"""
Loading trained bundles and predicting from a photo (used by the app and by
evaluate.py). A bundle is the checkpoint of ONE task: an ensemble of fold
models + the temperature and thresholds that were fitted on out-of-fold data.
"""

import os
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import torch
from PIL import Image

from calibration import sigmoid, status_from_prob
from dataset import EVAL_TRANSFORM
from model import build_model
from settings import STABILITY_ZOOMS


@dataclass
class Bundle:
    task: str
    class_names: List[str]
    models: list
    temperature: float
    thresholds: Dict[str, float]
    band: float
    device: torch.device
    meta: dict
    gate: Optional[dict] = None


def load_bundle(path: str, device: Optional[torch.device] = None) -> Optional[Bundle]:
    """Returns None if the checkpoint file doesn't exist."""
    if not os.path.exists(path):
        return None
    device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ckpt = torch.load(path, map_location=device, weights_only=False)  # our own trusted file
    models_ = []
    for state in ckpt["state_dicts"]:
        m = build_model(ckpt["task"], pretrained=False).to(device)
        m.load_state_dict(state)
        m.eval()
        models_.append(m)
    return Bundle(
        task=ckpt["task"],
        class_names=ckpt["class_names"],
        models=models_,
        temperature=float(ckpt.get("temperature", 1.0)),
        thresholds=ckpt.get("thresholds", {c: 0.5 for c in ckpt["class_names"]}),
        band=float(ckpt.get("uncertain_band", 0.1)),
        device=device,
        meta={k: ckpt.get(k) for k in ("cv_metrics", "args", "n_train", "model_version", "preprocessing", "feature_schema")},
        gate=ckpt.get("gate"),
    )


@torch.no_grad()
def ensemble_logits(bundle: Bundle, batch: torch.Tensor) -> np.ndarray:
    """Average the raw logits of all ensemble members -> (B, n_classes)."""
    batch = batch.to(bundle.device)
    logits = torch.stack([m(batch) for m in bundle.models]).mean(0)
    return logits.cpu().numpy()


def calibrated_probs(bundle: Bundle, logits: np.ndarray) -> np.ndarray:
    return sigmoid(logits / bundle.temperature)


def predict(bundle: Bundle, image: Image.Image) -> Dict[str, dict]:
    """Per condition: calibrated probability, threshold and True/False/None status."""
    tensor = EVAL_TRANSFORM(image.convert("RGB")).unsqueeze(0)
    probs = calibrated_probs(bundle, ensemble_logits(bundle, tensor))[0]
    result = {}
    for name, p in zip(bundle.class_names, probs):
        t = bundle.thresholds.get(name, 0.5)
        result[name] = {
            "prob": float(p),
            "threshold": float(t),
            "status": status_from_prob(float(p), t, bundle.band),
        }
    return result


def familiarity(bundle: Bundle, image: Image.Image) -> Optional[dict]:
    """How much does this photo look like the training photos? None if the checkpoint has no gate."""
    if not bundle.gate:
        return None
    from gate import embed_image, gate_check  # local import keeps torchvision weights loading lazy
    return gate_check(bundle.gate, embed_image(image, bundle.device, bundle.gate.get("extractor")))


def predict_stable(bundle: Bundle, image: Image.Image) -> Dict[str, dict]:
    """Like predict(), plus a stability check: the same photo is also tried slightly
    shifted/zoomed/mirrored. 'spread' is the largest probability gap between those versions.
    A big spread means the answer depends on tiny changes -> treat it as unsure."""
    rgb = image.convert("RGB")
    w, h = rgb.size
    views = [rgb, rgb.transpose(Image.Transpose.FLIP_LEFT_RIGHT)]
    for f in STABILITY_ZOOMS:
        cw, ch = int(w * f), int(h * f)
        left, top = (w - cw) // 2, (h - ch) // 2
        views.append(rgb.crop((left, top, left + cw, top + ch)))
    batch = torch.stack([EVAL_TRANSFORM(v) for v in views])
    probs = calibrated_probs(bundle, ensemble_logits(bundle, batch))  # (views, classes)
    out = {}
    for j, name in enumerate(bundle.class_names):
        t = bundle.thresholds.get(name, 0.5)
        p = float(probs[0, j])
        out[name] = {
            "prob": p, "threshold": float(t),
            "status": status_from_prob(p, t, bundle.band),
            "spread": float(probs[:, j].max() - probs[:, j].min()),
            "views_positive": int((probs[:, j] >= t).sum()), "n_views": int(len(views)),
        }
    return out


def image_quality(image: Image.Image) -> dict:
    """Cheap measurements that explain a poor result. verdict.quality_flags() turns them into flags."""
    rgb = image.convert("RGB")
    w, h = rgb.size
    gray = np.asarray(rgb.convert("L"), dtype=np.float32)
    brightness = float(gray.mean())
    # variance of a Laplacian-style second derivative = sharpness
    lap = (-4 * gray[1:-1, 1:-1] + gray[:-2, 1:-1] + gray[2:, 1:-1] + gray[1:-1, :-2] + gray[1:-1, 2:])
    sharpness = float(lap.var()) if lap.size else 0.0
    return {"width": w, "height": h, "brightness": brightness, "sharpness": sharpness}
