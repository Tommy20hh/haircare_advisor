"""Run: python tests/test_verdict.py   (no torch needed)"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import verdict
from verdict import advice_keys, decide, quality_flags

# default: no phone validation -> reliability is never 'good'
assert decide({'status': False, 'spread': 0.0}, 'familiar', [])['reliability'] == 'limited'
assert 'untested' in decide({'status': False, 'spread': 0.0}, 'familiar', [])['reasons']
verdict.PHONE_VALIDATED = True   # the rest checks the full rule set as if validated

def d(status, tier="familiar", spread=0.0, flags=()):
    return decide({"status": status, "spread": spread}, tier, list(flags))

# 1. unfamiliar photos never get a reassuring answer
assert d(False, "very_unfamiliar")["verdict"] == "unsuitable"
assert d(False, "unfamiliar")["verdict"] == "unsure"
assert d(False, "familiar", flags=["blurry"])["verdict"] == "unsure"
# 2. normal good case
assert d(False)["verdict"] == "none_seen" and d(False)["reliability"] == "good"
assert d(True)["verdict"] == "possible" and d(True)["reliability"] == "good"
# 3. close call and unstable answers
assert d(None)["verdict"] == "unsure"
assert d(True, spread=0.4)["verdict"] == "unsure"
assert d(True, spread=0.2)["reliability"] == "limited"
# 4. no gate in checkpoint -> never 'good'
assert d(False, tier=None)["verdict"] == "unsure"   # cannot verify the photo -> never reassure
assert d(True, tier=None)["reliability"] == "limited"
# 5. quality flags
assert quality_flags({"width": 100, "height": 500, "brightness": 30, "sharpness": 5}) == ["small", "dark", "blurry"]
# 5b. a plain/blank picture is refused even when the familiarity check says "familiar"
from verdict import photo_status
assert quality_flags({"width": 640, "height": 480, "brightness": 120, "sharpness": 0.0}) == ["blank", "blurry"]
assert photo_status("familiar", ["blank", "blurry"]) == "mismatch"
assert photo_status("familiar", ["blurry"]) == "partial"
# 6. advice
v = {"balding": d(False), "dryness": d(True), "dandruff": d(None), "low_density": d(True)}
k = advice_keys(v, [])
assert "tip:dryness" in k and "retake:dandruff" in k and "multi" in k and "general" not in k
assert advice_keys({"balding": d(False)}, ["dryness"]) == ["general", "not_assessed"]
print("verdict tests passed")
