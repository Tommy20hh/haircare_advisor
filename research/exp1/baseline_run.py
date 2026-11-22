"""Experiment 1 - runs the EXISTING gate + quality checks (method A) on the stimuli. Laptop CPU, production environment, read-only.
Uses the deployed crown (scalp) checkpoint and src/pipeline.assess exactly as the app does. Never reads labels.
  python research\\exp1\\baseline_run.py            -> research\\exp1\\results\\baseline_predictions.csv"""
import csv, os, sys, time
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from PIL import Image
from inference import load_bundle
from pipeline import assess
E1 = os.path.join(ROOT, "research", "exp1"); bundle = load_bundle(os.path.join(ROOT, "checkpoints", "scalp_model.pt"))
rows = list(csv.DictReader(open(os.path.join(E1, "stimuli", "manifest_public.csv"), newline="")))
os.makedirs(os.path.join(E1, "results"), exist_ok=True); out = []
for r in rows:
    t = time.time(); o = assess(bundle, Image.open(os.path.join(E1, "stimuli", r["file"])).convert("RGB"))
    out.append({"stim_id": r["stim_id"], "status": o["status"], "tier": o["tier"], "flags": "|".join(o["flags"]), "distance": (o["fam"] or {}).get("distance", ""), "seconds": round(time.time() - t, 3)})
with open(os.path.join(E1, "results", "baseline_predictions.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
print("wrote", len(out), "rows")
