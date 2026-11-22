"""Experiment 0 - verify the frozen scalp/balding test splits. Standard library only (no torch needed).
Run from the project root:   python research/exp0/verify_split.py
Exit code 0 = all checks pass. Read-only: it never writes to data/."""
import csv, hashlib, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
EXPECT = {"data/scalp_labels.csv": "e0390abb4cafb7768f19cbe68ac8a46b654fe02d38144871554f83284754fd9e",
          "data/balding_labels.csv": "0215a9723b7d7f48ff52f5bb261d6acd0aa4b04fcbdf2ec5b072da3486bbbb16"}
ok = True
def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
def rows(p): return list(csv.DictReader(open(p, newline="", encoding="utf-8")))
def check(name, cond, detail=""):
    global ok; ok &= bool(cond); print(("PASS " if cond else "FAIL ") + name + (" - " + detail if detail else ""))
for rel, h in EXPECT.items():
    check("sha256 " + rel, sha(os.path.join(ROOT, rel)) == h, sha(os.path.join(ROOT, rel))[:12])
s = rows(os.path.join(ROOT, "data/scalp_labels.csv"))
tr = [r for r in s if r["split"] == "train"]; te = [r for r in s if r["split"] == "test"]
check("scalp rows 883 = 709 train + 174 test", len(s) == 883 and len(tr) == 709 and len(te) == 174, f"{len(tr)}+{len(te)}")
check("scalp no duplicate filepaths", len({r["filepath"] for r in s}) == len(s))
check("scalp no train/test filepath overlap", not ({r["filepath"] for r in tr} & {r["filepath"] for r in te}))
check("scalp no train/test group overlap", not ({r["group"] for r in tr} & {r["group"] for r in te}))
hd = [r for r in te if r["source"] == "roboflow_hairdata"]
pos = lambda c: sum(r[c] == "1.0" or r[c] == "1" for r in hd)
check("hairdata test = 37 (10/16/15 positives)", len(hd) == 37 and (pos("dryness"), pos("dandruff"), pos("low_density")) == (10, 16, 15),
      f"{len(hd)} {pos('dryness')}/{pos('dandruff')}/{pos('low_density')}")
b = rows(os.path.join(ROOT, "data/balding_labels.csv")); bt = [r for r in b if r["split"] == "test"]
check("balding test = 841", len(bt) == 841, str(len(bt)))
check("balding no train/test group overlap", not ({r["group"] for r in b if r["split"] != "test"} & {r["group"] for r in bt}))
for name, sub in (("scalp_test_174.csv", te), ("scalp_hairdata_test_37.csv", hd), ("balding_test_841.csv", bt)):
    fp = os.path.join(HERE, "frozen_lists", name); fz = rows(fp)
    check("frozen list matches " + name, [r["filepath"] for r in fz] == [r["filepath"] for r in sub])

RAW = sys.argv[1] if len(sys.argv) > 1 else r"C:\Haircare\kaggle_upload\raw"
if os.path.isdir(RAW):
    for name in ("scalp_test_174.csv", "balding_test_841.csv"):
        miss = [r["filepath"] for r in rows(os.path.join(HERE, "frozen_lists", name)) if not os.path.isfile(os.path.join(RAW, r["filepath"]))]
        check("every photo of " + name + " exists under " + RAW, not miss, f"{len(miss)} missing" + (": " + miss[0] if miss else ""))
else:
    print("SKIP photo-existence check (raw folder not found: " + RAW + ")")
print("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED"); sys.exit(0 if ok else 1)
