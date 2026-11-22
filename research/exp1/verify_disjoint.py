"""Experiment 1 - proves dev and final sets do not overlap (by photo, by group, and for synthetic variants by original).
  python research\\exp1\\verify_disjoint.py --simulate     BEFORE generating anything: re-derives the selection from data\\*.csv (no images needed)
  python research\\exp1\\verify_disjoint.py                 AFTER generating: checks private\\manifest_private.csv (also after the synthetic phase)
Exit code 0 = every check passed. Read-only."""
import argparse, os, sys
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
from build_stimuli import choose
ok = True
def check(name, cond, detail=""):
    global ok; ok &= bool(cond); print(("PASS " if cond else "FAIL ") + name + (" - " + detail if detail else ""))
ap = argparse.ArgumentParser(); ap.add_argument("--simulate", action="store_true"); ap.add_argument("--faces", type=int, default=0); a = ap.parse_args()
sc = pd.read_csv(os.path.join(ROOT, "data", "scalp_labels.csv")); ba = pd.read_csv(os.path.join(ROOT, "data", "balding_labels.csv"))
frozen = pd.read_csv(os.path.join(HERE, "..", "exp0", "frozen_lists", "scalp_test_174.csv"))
if a.simulate:
    c = choose(sc, ba, 42, a.faces); fin = pd.concat([c["final_scalp"], c["final_faces"]]); dev = pd.concat([c["dev_scalp"], c["dev_faces"]])
    check("final scalp photos = the 174 frozen test photos", set(c["final_scalp"].filepath) == set(frozen.filepath) and len(c["final_scalp"]) == 174, str(len(c["final_scalp"])))
    check("dev scalp photos are all train rows", (c["dev_scalp"]["split"] == "train").all(), f"{len(c['dev_scalp'])} photos")
    check("dev and final share no photo (filepath)", not (set(dev.filepath) & set(fin.filepath)))
    g = lambda d: set(zip(d.get("source", ["x"] * len(d)), d["group"]))
    check("dev and final share no group id", not (set(dev["group"]) & set(fin["group"])), f"{len(set(dev['group']) & set(fin['group']))} shared")
    check("synthetic dev originals are inside the dev set", set(c["dev_syn_originals"].filepath) <= set(c["dev_scalp"].filepath))
    check("faces (if any) dev=train rows, final=test rows", (c["dev_faces"]["split"] == "train").all() and (c["final_faces"]["split"] == "test").all() if len(c["dev_faces"]) + len(c["final_faces"]) else True, f"faces={len(c['final_faces'])}")
    print("per-source dev counts:", c["dev_scalp"].source.value_counts().to_dict()); print("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED"); sys.exit(0 if ok else 1)
pm = pd.read_csv(os.path.join(HERE, "private", "manifest_private.csv"), dtype=str).fillna("")
dev, fin, syn = pm[pm["set"] == "dev"], pm[pm["set"] == "final_natural"], pm[pm["set"] == "final_synth"]
check("stim_ids unique", pm.stim_id.is_unique)
if len(fin) == 0:  # DEV-ONLY stage: no final photos were generated; compare the dev photos with the frozen test rows directly
    tst = sc[sc["split"] == "test"]; dn = dev[dev.kind == "natural"]
    check("no final-evaluation photos were generated yet", len(fin) == 0 and len(syn) == 0)
    check("dev natural photos: exactly 36", len(dn) == 36, str(len(dn)))
    check("dev: 12 per source", dn.source.value_counts().to_dict() == {"roboflow_hairdata": 12, "healthy_scalp": 12, "extra_dandruff_big_chunks": 12}, str(dn.source.value_counts().to_dict()))
    check("dev photos are all train rows in data/scalp_labels.csv", set(dn.filepath) <= set(sc[sc["split"] == "train"].filepath) and (dn.orig_split == "train").all())
    check("dev shares no photo with the 174 frozen test photos", not (set(dn.filepath) & set(frozen.filepath)), f"{len(set(dn.filepath) & set(frozen.filepath))} shared")
    check("dev shares no group id with any test row", not (set(dn.group.astype(str)) & set(tst.group.astype(str))), f"{len(set(dn.group.astype(str)) & set(tst.group.astype(str)))} shared")
    check("public manifest has only stim_id/set/file", list(pd.read_csv(os.path.join(HERE, "stimuli", "manifest_public.csv"), nrows=1).columns) == ["stim_id", "set", "file"])
    miss = [f for f in dn.file if not os.path.exists(os.path.join(HERE, "stimuli", f))]
    check("every dev image file exists", not miss, f"{len(miss)} missing")
    bad = []
    for line in open(os.path.join(HERE, "stimuli", "CHECKSUMS.sha256")):
        h, f = line.rstrip("\n").split("  ", 1)
        import hashlib; p = os.path.join(HERE, "stimuli", f)
        if not os.path.exists(p) or hashlib.sha256(open(p, "rb").read()).hexdigest() != h: bad.append(f)
    check("checksums match the files on disk", not bad, f"{len(bad)} mismatches")
    for rn in ("rater1", "rater2"):
        rs = pd.read_csv(os.path.join(HERE, "private", f"rating_dev_{rn}.csv"), dtype=str)
        check(f"rating sheet {rn}: the same 36 photos, no labels pre-filled", set(rs.stim_id) == set(dn.stim_id) and rs.label.isna().all())
    print("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED"); sys.exit(0 if ok else 1)
check("dev and final natural share no photo", not (set(dev.filepath) & set(fin.filepath)))
check("dev and final share no group", not (set(dev.group) & set(fin.group)))
check("dev natural originals are train rows only", (dev[dev.kind == "natural"].orig_split == "train").all())
check("final natural are test rows only", (fin.orig_split == "test").all())
check("final natural scalp photos are exactly the frozen list", set(fin[fin.source != "kaggle_balding"].filepath) == set(frozen.filepath))
dsyn = dev[dev.kind.str.startswith("synthetic")]
check("dev synthetic originals are dev natural photos", set(dsyn.original_id) <= set(dev[dev.kind == "natural"].stim_id))
if len(syn):
    check("final synthetic originals are final natural photos", set(syn.original_id) <= set(fin.stim_id))
    check("no original used by both dev and final variants", not (set(dsyn.original_id) & set(syn.original_id)))
    check("no final synthetic variant derives from a dev photo", not (set(syn.filepath) & set(dev.filepath)) and not (set(syn.group) & set(dev.group)))
    check("every synthetic variant has an original", (syn.original_id != "").all())
print("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED"); sys.exit(0 if ok else 1)
