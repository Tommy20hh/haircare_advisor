"""Tests the numpy parts of the familiarity gate and region layout with torch stubbed out.
Run: python tests/test_gate_logic.py"""
import os, sys, types
from unittest.mock import MagicMock
import numpy as np
from PIL import Image
for name in ["torch", "torch.nn", "torch.nn.functional", "torchvision", "torchvision.models", "torchvision.transforms"]:
    sys.modules[name] = MagicMock()
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
ds = types.ModuleType("dataset"); ds.EVAL_TRANSFORM = MagicMock(); sys.modules["dataset"] = ds
for m in ("model", "calibration"):
    mod = types.ModuleType(m); sys.modules[m] = mod
sys.modules["model"].build_model = lambda *a, **k: None
sys.modules["calibration"].sigmoid = lambda x: x; sys.modules["calibration"].status_from_prob = lambda *a: None
import gate, inference

rng = np.random.default_rng(0)
def unit(x): return x / np.linalg.norm(x, axis=1, keepdims=True)
centre = rng.normal(size=(1, 64))
bank = unit(centre + 0.3 * rng.normal(size=(300, 64))).astype(np.float32)
groups = np.arange(300)
g = gate.build_gate(bank, groups, k=5)
assert g["familiar_max"] < g["unfamiliar_max"]
near = unit(centre + 0.3 * rng.normal(size=(1, 64))).astype(np.float32)[0]
far = unit(rng.normal(size=(1, 64))).astype(np.float32)[0]
assert gate.gate_check(g, near)["tier"] == "familiar", gate.gate_check(g, near)
assert gate.gate_check(g, far)["tier"] in ("unfamiliar", "very_unfamiliar")
# near-duplicates in the same group must be ignored when judging a training photo
bank2 = np.concatenate([bank, bank[:10]]); groups2 = np.concatenate([np.arange(300), np.arange(10)])
d_with = gate.knn_distance(bank2, bank2[:10], k=1, exclude=(groups2, groups2[:10]))
d_without = gate.knn_distance(bank2, bank2[:10], k=1)
assert d_without.max() < 1e-3 and d_with.min() > 0.001
print("gate logic tests passed")
