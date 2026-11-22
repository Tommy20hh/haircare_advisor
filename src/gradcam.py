"""
Grad-CAM: a heatmap of WHERE the model looked for a given condition.
Used in the app so users (and your professor) can see that the model is looking
at hair/scalp rather than glasses, background or the wall.
"""

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

from dataset import EVAL_TRANSFORM


def grad_cam(model, tensor: torch.Tensor, class_idx: int) -> np.ndarray:
    """Returns a (H, W) heatmap in [0, 1] at the model's input resolution.
    `model` is one ConditionClassifier; `tensor` is (1, 3, H, W) on the same device."""
    model.eval()
    store = {}
    layer = model.backbone.features[-1]

    def fwd_hook(_, __, output):
        store["act"] = output
        output.register_hook(lambda g: store.__setitem__("grad", g))

    handle = layer.register_forward_hook(fwd_hook)
    try:
        with torch.enable_grad():
            x = tensor.clone().requires_grad_(True)
            logits = model(x)
            model.zero_grad(set_to_none=True)
            logits[0, class_idx].backward()
    finally:
        handle.remove()

    act, grad = store["act"].detach(), store["grad"].detach()
    weights = grad.mean(dim=(2, 3), keepdim=True)
    cam = F.relu((weights * act).sum(dim=1, keepdim=True))
    cam = F.interpolate(cam, size=tensor.shape[-2:], mode="bilinear", align_corners=False)[0, 0]
    cam = cam - cam.min()
    cam = cam / cam.max().clamp(min=1e-8)
    return cam.cpu().numpy()


def overlay_heatmap(image: Image.Image, cam: np.ndarray, alpha: float = 0.45) -> Image.Image:
    """Blend the heatmap onto the original photo (resized to the cam size)."""
    import matplotlib

    base = image.convert("RGB").resize((cam.shape[1], cam.shape[0]))
    heat = (matplotlib.colormaps["jet"](cam)[..., :3] * 255).astype(np.uint8)
    blended = (np.asarray(base) * (1 - alpha) + heat * alpha).astype(np.uint8)
    return Image.fromarray(blended)


def explain(bundle, image: Image.Image, class_name: str) -> Image.Image:
    """Heatmap overlay for one condition, averaged over the ensemble members."""
    tensor = EVAL_TRANSFORM(image.convert("RGB")).unsqueeze(0).to(bundle.device)
    idx = bundle.class_names.index(class_name)
    cams = [grad_cam(m, tensor, idx) for m in bundle.models]
    return overlay_heatmap(image, np.mean(cams, axis=0))
