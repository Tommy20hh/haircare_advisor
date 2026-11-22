"""
"Does this photo look like anything the model was trained on?"  (familiarity gate)

The classifiers only know the style of their training photos. For a photo that
looks very different (far away, a whole room, odd lighting) any answer would be a
guess, even if it looks confident. The gate measures how unfamiliar a photo is:

  1. Every training photo is turned into a 1280-number "fingerprint" by the
     ImageNet-pretrained MobileNetV2 (NOT the fine-tuned one - it is a neutral
     judge of overall look: colours, textures, framing).
  2. For a new photo we find its k nearest training fingerprints (cosine distance).
  3. We compare that distance with how far apart training photos normally are
     (leave-one-out, ignoring their own near-duplicates).

Result tiers: "familiar" | "unfamiliar" | "very_unfamiliar". The tier limits come
from the training data (percentiles), see build_gate.py; they are a safety net,
not a proof of accuracy.
"""

from typing import Dict, Optional, Sequence

import numpy as np
import torch
from PIL import Image
from torchvision import models

from dataset import EVAL_TRANSFORM

_EXTRACTOR = {}


def _extractor(device, state=None):
    """The neutral ImageNet feature extractor. With `state` (stored inside the checkpoint) no
    internet is needed; without it the standard ImageNet weights are downloaded once."""
    key = (str(device), state is not None)
    if key not in _EXTRACTOR:
        if state is not None:
            m = models.mobilenet_v2(weights=None).features
            m.load_state_dict(state)
        else:
            m = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.DEFAULT).features
        _EXTRACTOR[key] = m.to(device).eval()
    return _EXTRACTOR[key]


@torch.no_grad()
def embed_batch(batch: torch.Tensor, device, state=None) -> np.ndarray:
    f = _extractor(device, state)(batch.to(device))
    f = torch.nn.functional.adaptive_avg_pool2d(f, 1).flatten(1)
    f = torch.nn.functional.normalize(f, dim=1)
    return f.cpu().numpy().astype(np.float32)


def embed_image(image: Image.Image, device, state=None) -> np.ndarray:
    return embed_batch(EVAL_TRANSFORM(image.convert("RGB")).unsqueeze(0), device, state)[0]


def knn_distance(bank: np.ndarray, feats: np.ndarray, k: int = 5, exclude: Optional[np.ndarray] = None) -> np.ndarray:
    """Mean cosine distance to the k closest bank entries. `exclude[i]` = group ids to ignore for query i's own group."""
    sims = feats @ bank.T  # both L2-normalised
    out = np.empty(len(feats), dtype=np.float32)
    for i in range(len(feats)):
        s = sims[i]
        if exclude is not None:
            s = np.where(exclude[0] == exclude[1][i], -np.inf, s)  # same group (itself/near-duplicates) removed
        top = np.sort(s)[-k:]
        out[i] = float(1.0 - top.mean())
    return out


def build_gate(bank: np.ndarray, groups: Sequence[int], k: int = 5) -> Dict:
    groups = np.asarray(groups)
    d = knn_distance(bank, bank, k=k, exclude=(groups, groups))
    return {
        "bank": bank.astype(np.float16),
        "k": k,
        "familiar_max": float(np.percentile(d, 95)),       # as typical as 95% of training photos
        "unfamiliar_max": float(np.percentile(d, 99.5) * 1.25),  # beyond this: very unfamiliar
        "train_distance_percentiles": {str(q): float(np.percentile(d, q)) for q in (50, 90, 95, 99, 99.5)},
    }


def gate_check(gate: Dict, feat: np.ndarray) -> Dict:
    bank = gate["bank"].astype(np.float32)
    dist = float(knn_distance(bank, feat[None, :], k=gate["k"])[0])
    if dist <= gate["familiar_max"]:
        tier = "familiar"
    elif dist <= gate["unfamiliar_max"]:
        tier = "unfamiliar"
    else:
        tier = "very_unfamiliar"
    return {"distance": dist, "tier": tier, "familiar_max": gate["familiar_max"], "unfamiliar_max": gate["unfamiliar_max"]}
