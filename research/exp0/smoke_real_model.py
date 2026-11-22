"""Experiment 0 - real-model smoke test (read-only). Loads the DEPLOYED checkpoints through the real Engine, runs the full
pipeline (quality flags -> familiarity gate -> 5-view stability -> verdict) on a few frozen TEST photos, and writes
research\\exp0\\smoke_real_model.json. Photos stay on this computer. Does not start the server or change any file but its output.
  python research\\exp0\\smoke_real_model.py --raw <RAW_ROOT>
"""
import argparse, csv, json, os, sys, time
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src")); sys.path.insert(0, ROOT)
from PIL import Image
from service.engine import Engine
p = argparse.ArgumentParser(); p.add_argument("--raw", required=True); p.add_argument("--n", type=int, default=3); a = p.parse_args()
fz = os.path.join(ROOT, "research", "exp0", "frozen_lists")
def pick(name, n): return list(csv.DictReader(open(os.path.join(fz, name), newline="")))[:n]
t0 = time.time(); eng = Engine(os.path.join(ROOT, "checkpoints")); eng.warm_up(); load_s = round(time.time() - t0, 1)
res = {"load_seconds": load_s, "slots_loaded": sorted(eng.bundles), "cases": []}
for slot, name in (("crown", "scalp_hairdata_test_37.csv"), ("front", "balding_test_841.csv")):
    for r in pick(name, a.n):
        t1 = time.time(); out = eng.assess(slot, Image.open(os.path.join(a.raw, r["filepath"])).convert("RGB"))
        res["cases"].append({"slot": slot, "filepath": r["filepath"], "seconds": round(time.time() - t1, 2), "status": out.get("status"), "tier": out.get("tier"),
                             "flags": out.get("flags"), "verdicts": {k: ({"verdict": v.get("verdict"), "reliability": v.get("reliability")} if isinstance(v, dict) else str(v)) for k, v in (out.get("verdicts") or {}).items()}})
json.dump(res, open(os.path.join(ROOT, "research", "exp0", "smoke_real_model.json"), "w"), indent=2, default=str); print(json.dumps(res, indent=2, default=str))
