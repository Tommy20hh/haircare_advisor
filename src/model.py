"""
Hair / scalp condition classifiers.

TWO separate models, one per photo type, each trained ONLY on data that was
really labelled for it (no cross-dataset label filling):

    balding : front photo of the head/face   -> [balding]
    scalp   : close-up photo of the scalp    -> [dryness, dandruff, low_density]

Both use the same lightweight backbone: MobileNetV2 pretrained on ImageNet
(transfer learning), with the final layer replaced by a small head.
Outputs are raw logits; sigmoid turns them into independent probabilities
(a scalp photo can show dryness AND dandruff at once, so not softmax).
"""

import torch
import torch.nn as nn
from torchvision import models

TASKS = {
    "balding": ["balding"],
    "scalp": ["dryness", "dandruff", "low_density"],
}


class ConditionClassifier(nn.Module):
    def __init__(self, num_classes: int, pretrained: bool = True, dropout: float = 0.3):
        super().__init__()
        weights = models.MobileNet_V2_Weights.DEFAULT if pretrained else None
        backbone = models.mobilenet_v2(weights=weights)
        in_features = backbone.classifier[1].in_features
        backbone.classifier = nn.Sequential(nn.Dropout(dropout), nn.Linear(in_features, num_classes))
        self.backbone = backbone

    def pooled(self, x: torch.Tensor) -> torch.Tensor:
        """The 1280-number summary of a photo that the final layer reads."""
        f = self.backbone.features(x)
        return torch.flatten(nn.functional.adaptive_avg_pool2d(f, 1), 1)

    def head(self, pooled: torch.Tensor) -> torch.Tensor:
        return self.backbone.classifier(pooled)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.backbone(x)  # raw logits

    def set_backbone_frozen(self, frozen: bool) -> None:
        """Freeze/unfreeze the pretrained feature extractor (the head always trains)."""
        for p in self.backbone.features.parameters():
            p.requires_grad = not frozen


class _GradReverse(torch.autograd.Function):
    """Identity going forward; flips (and scales) the gradient going backward."""
    @staticmethod
    def forward(ctx, x, lam):
        ctx.lam = lam
        return x.view_as(x)

    @staticmethod
    def backward(ctx, grad):
        return -ctx.lam * grad, None


def grad_reverse(x: torch.Tensor, lam: float) -> torch.Tensor:
    return _GradReverse.apply(x, lam)


def build_model(task: str, pretrained: bool = True) -> ConditionClassifier:
    if task not in TASKS:
        raise ValueError(f"Unknown task {task!r}; expected one of {list(TASKS)}")
    return ConditionClassifier(num_classes=len(TASKS[task]), pretrained=pretrained)


if __name__ == "__main__":
    for t, names in TASKS.items():
        m = build_model(t, pretrained=False)
        out = m(torch.randn(2, 3, 224, 224))
        print(t, names, "->", tuple(out.shape))
