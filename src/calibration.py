"""
Post-training calibration helpers (used by train.py, evaluate.py and the app).

* fit_temperature  : one scalar T so that sigmoid(logit / T) is an honest
                     probability (fixes the over-confidence that class-weighted
                     training causes).
* tune_thresholds  : a decision threshold per condition, chosen on held-out
                     (out-of-fold) predictions instead of a blind 0.5.
* status_from_prob : True / False / None ("inconclusive") using that threshold
                     and an uncertainty band around it.
"""

from typing import Dict, List, Optional

import numpy as np


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -50, 50)))


def masked_nll(logits, labels, mask, temperature: float) -> float:
    p = np.clip(sigmoid(logits / temperature), 1e-6, 1 - 1e-6)
    nll = -(labels * np.log(p) + (1 - labels) * np.log(1 - p))
    return float((nll * mask).sum() / max(mask.sum(), 1))


def fit_temperature(logits: np.ndarray, labels: np.ndarray, mask: np.ndarray) -> float:
    """Grid-search the single temperature that minimises log-loss. T>1 softens
    over-confident outputs; T<1 sharpens under-confident ones."""
    grid = np.linspace(0.3, 6.0, 115)
    losses = [masked_nll(logits, labels, mask, t) for t in grid]
    return float(grid[int(np.argmin(losses))])


def _f1(y, pred):
    tp = int(((y == 1) & (pred == 1)).sum())
    fp = int(((y == 0) & (pred == 1)).sum())
    fn = int(((y == 1) & (pred == 0)).sum())
    return 2 * tp / max(2 * tp + fp + fn, 1)


def tune_thresholds(probs: np.ndarray, labels: np.ndarray, mask: np.ndarray,
                    class_names: List[str], min_positives: int = 5) -> Dict[str, float]:
    """Per-class threshold that maximises F1 on out-of-fold predictions.
    Falls back to 0.5 when a class has too few positives to tune on."""
    out = {}
    for i, name in enumerate(class_names):
        m = mask[:, i] == 1
        y, p = labels[m, i], probs[m, i]
        if int(y.sum()) < min_positives or int((1 - y).sum()) < min_positives:
            out[name] = 0.5
            continue
        best_t, best_f1 = 0.5, -1.0
        for t in np.arange(0.05, 0.951, 0.01):
            f1 = _f1(y, (p >= t).astype(int))
            # prefer the threshold closest to 0.5 when F1 ties
            if f1 > best_f1 + 1e-9 or (abs(f1 - best_f1) <= 1e-9 and abs(t - 0.5) < abs(best_t - 0.5)):
                best_t, best_f1 = float(t), f1
        out[name] = round(best_t, 2)
    return out


def status_from_prob(prob: float, threshold: float, band: float) -> Optional[bool]:
    """True = detected, False = not detected, None = too close to call."""
    if prob >= threshold + band:
        return True
    if prob <= threshold - band:
        return False
    return None
