"""
Builds web/data/accuracy.json (shown in the website's 'Accuracy and limits') from a real
evaluate.py metrics.json. Only the within-source (style-free) AUROCs are used.

    python scripts/make_accuracy_summary.py --metrics results/scalp/metrics.json --source roboflow_hairdata ^
        --out web/data/accuracy.json
Run it again with another --metrics/--source and --append to add the balding model.
"""
import argparse
import json
import os

a = argparse.ArgumentParser()
a.add_argument("--metrics", required=True)
a.add_argument("--source", required=True, help="source name inside within_source_auroc")
a.add_argument("--out", default="web/data/accuracy.json")
a.add_argument("--append", action="store_true")
args = a.parse_args()

m = json.load(open(args.metrics))
items = []
for name, r in m.items():
    w = (r.get("within_source_auroc") or {}).get(args.source)
    if not w or not w.get("auroc_95ci"):
        print(f"skip {name}: no within-source result for {args.source}")
        continue
    items.append({"name": name, "auroc": w["auroc"], "lo": w["auroc_95ci"][0], "hi": w["auroc_95ci"][1],
                  "n": w["n"], "pos": w["n_pos"]})
old = []
if args.append and os.path.exists(args.out):
    old = json.load(open(args.out)).get("items", [])
os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
json.dump({"source": args.source, "items": old + items}, open(args.out, "w"), indent=2)
print(json.dumps(old + items, indent=2))
