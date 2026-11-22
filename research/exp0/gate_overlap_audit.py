"""Experiment 0 - READ-ONLY audit: was the deployed familiarity gate built from any frozen test photo?

How it works (no rebuilding, nothing is written into checkpoints or data/):
 1. Load the deployed checkpoint and its stored gate (`bank` = one 1280-number fingerprint per photo it was built from).
 2. Re-compute the same fingerprint (stored ImageNet extractor + EVAL_TRANSFORM, exactly as build_gate.py) for every
    train photo and every frozen TEST photo listed in the label file.
 3. A photo that was used to build the gate has a bank row with cosine similarity ~1.0 (the bank is stored in float16).
    * POSITIVE CONTROL: every train photo should match its own bank row (in file order) at >= EXACT.
    * TEST PHOTOS: count how many reach >= EXACT (content identical to a bank row) or >= NEAR (near twin).

Run from the project root, with the same Python you used for evaluate.py:
  python research\\exp0\\gate_overlap_audit.py --task scalp   --labels data\\scalp_labels.csv   --img-dir <RAW_ROOT> --checkpoint checkpoints\\scalp_model.pt
  python research\\exp0\\gate_overlap_audit.py --task balding --labels data\\balding_labels.csv --img-dir <RAW_ROOT> --checkpoint checkpoints\\balding_model.pt
Output: research\\exp0\\gate_audit_<task>.json and gate_audit_<task>_rows.csv
"""
import argparse, csv, json, os, sys
import numpy as np, torch
from torch.utils.data import DataLoader
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from dataset import ConditionDataset, EVAL_TRANSFORM, read_labels  # noqa: E402
from gate import _extractor, embed_batch  # noqa: E402
from model import TASKS  # noqa: E402
EXACT, NEAR = 0.9995, 0.98

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--task", required=True, choices=list(TASKS)); p.add_argument("--labels", required=True)
    p.add_argument("--img-dir", required=True); p.add_argument("--checkpoint", required=True)
    p.add_argument("--num-workers", type=int, default=2)
    a = p.parse_args()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ck = torch.load(a.checkpoint, map_location="cpu", weights_only=False)
    gate = ck["gate"]; bank = gate["bank"].astype(np.float32)
    state = gate["extractor"]; _extractor(device, state)
    df = read_labels(a.labels, TASKS[a.task])
    def embed(sub):
        ds = ConditionDataset(sub.reset_index(drop=True), a.img_dir, TASKS[a.task], EVAL_TRANSFORM)
        return np.concatenate([embed_batch(x, device, state) for x, _, _ in DataLoader(ds, batch_size=64, shuffle=False, num_workers=a.num_workers)])
    tr = df[df["split"].isin(["train", "val"])].reset_index(drop=True); te = df[df["split"] == "test"].reset_index(drop=True)
    out = {"task": a.task, "checkpoint": a.checkpoint, "bank_rows": int(len(bank)), "labels_train_val_rows": int(len(tr)), "test_rows": int(len(te)),
           "n_train_field": ck.get("n_train"), "thresholds": {"exact": EXACT, "near": NEAR}}
    rows = []
    if len(bank) == len(tr):
        ft = embed(tr); s = ft @ bank.T; best = s.argmax(1); mx = s.max(1)
        out["control"] = {"train_photos": len(tr), "own_row_matched_exact": int(sum(s[i, i] >= EXACT for i in range(len(tr)))),
                          "argmax_equals_own_row": int((best == np.arange(len(tr))).sum()), "min_own_similarity": float(np.min(np.diag(s))),
                          "bank_rows_unexplained_by_any_train_photo": int((s.max(0) < EXACT).sum())}
    else:
        out["control"] = {"note": "bank size != train/val rows in this label file; positive control skipped (this itself shows the gate was built from a different split)"}
    fe = embed(te); s = fe @ bank.T; best = s.argmax(1); mx = s.max(1)
    out["test"] = {"photos": len(te), "exact_matches": int((mx >= EXACT).sum()), "near_matches": int(((mx >= NEAR) & (mx < EXACT)).sum()),
                   "max_similarity": float(mx.max()), "median_similarity": float(np.median(mx))}
    if "source" in te.columns:
        out["test"]["by_source"] = {k: {"n": int((te.source == k).sum()), "exact": int(((te.source == k).to_numpy() & (mx >= EXACT)).sum()), "near": int(((te.source == k).to_numpy() & (mx >= NEAR) & (mx < EXACT)).sum())} for k in sorted(te.source.unique())}
    for i in range(len(te)):
        rows.append({"filepath": te.loc[i, "filepath"], "source": te.loc[i, "source"] if "source" in te.columns else "", "max_similarity": f"{mx[i]:.5f}", "nearest_bank_row": int(best[i]),
                     "nearest_train_photo": tr.loc[int(best[i]), "filepath"] if len(bank) == len(tr) else "", "class": "exact" if mx[i] >= EXACT else ("near" if mx[i] >= NEAR else "none")})
    base = os.path.join(ROOT, "research", "exp0", f"gate_audit_{a.task}")
    json.dump(out, open(base + ".json", "w"), indent=2)
    with open(base + "_rows.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()
