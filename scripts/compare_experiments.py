"""
Prints one table comparing experiments (for docs/experiment_log.md). Reads each
<results-root>/<experiment>/metrics.json and training summary if present.

    python scripts/compare_experiments.py --results-root results --source roboflow_hairdata
"""
import argparse
import json
import os

a = argparse.ArgumentParser()
a.add_argument("--results-root", default="results")
a.add_argument("--source", default="roboflow_hairdata")
args = a.parse_args()

rows = []
for exp in sorted(os.listdir(args.results_root)):
    p = os.path.join(args.results_root, exp, "metrics.json")
    if not os.path.exists(p):
        continue
    m = json.load(open(p))
    cells = []
    for c in ("dryness", "dandruff", "low_density"):
        w = ((m.get(c) or {}).get("within_source_auroc") or {}).get(args.source)
        cells.append(f"{w['auroc']} {w['auroc_95ci']}" if w and w.get("auroc_95ci") else "n/a")
    rows.append((exp, *cells))
print(f"Within-source AUROC (inside {args.source}) [95% CI]\n")
print("| experiment | dryness | dandruff | low_density |\n|---|---|---|---|")
for r in rows:
    print("| " + " | ".join(r) + " |")
