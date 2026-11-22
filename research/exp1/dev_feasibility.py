"""Experiment 1 - after the dev photos are rated: how many unsuitable photos can we expect among the 174 final photos?
  python research\\exp1\\dev_feasibility.py            (uses private\\rating_dev_rater1.csv, and rater2 + kappa if that file exists)
Read-only. A SMALL-SAMPLE ESTIMATE (12 photos per source): it is a planning signal, never a result."""
import os, sys, math
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); PRIV = os.path.join(HERE, "private")
TEST_N = {"roboflow_hairdata": 37, "healthy_scalp": 68, "extra_dandruff_big_chunks": 69}
def wilson(k, n, z=1.96):
    if n == 0: return (0.0, 1.0)
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)); return ((c - m) / d, (c + m) / d)
def load(rn):
    p = os.path.join(PRIV, f"rating_dev_{rn}_DONE.csv")  # the file downloaded from the rating page (preferred)
    if not os.path.exists(p): p = os.path.join(PRIV, f"rating_dev_{rn}.csv")
    if not os.path.exists(p): return None
    r = pd.read_csv(p, dtype=str).fillna(""); return r
pm = pd.read_csv(os.path.join(PRIV, "manifest_private.csv"), dtype=str).fillna(""); pm = pm[(pm["set"] == "dev") & (pm.kind == "natural")][["stim_id", "source"]]
r1 = load("rater1")
if r1 is None: sys.exit("rating_dev_rater1.csv not found in research\\exp1\\private\\")
r1 = r1[["stim_id", "label", "failure_category", "notes"]].merge(pm, on="stim_id")
if (r1.label == "").any(): sys.exit(f"{(r1.label == '').sum()} photos are still unrated in rater1 - finish the rating first")
bad = set(r1.label) - {"suitable", "unsuitable", "ambiguous"}
if bad: sys.exit(f"unexpected label words: {bad}")
lab = r1.set_index("stim_id").label
r2 = load("rater2")
if r2 is not None and not (r2.label == "").any():
    r2 = r2.set_index("stim_id").label.reindex(lab.index); agree = (lab == r2).mean()
    cats = ["suitable", "unsuitable", "ambiguous"]; po = agree; pe = sum((lab == c).mean() * (r2 == c).mean() for c in cats)
    kappa = (po - pe) / (1 - pe) if pe < 1 else float("nan"); print(f"Two raters: raw agreement {agree:.2f}, Cohen's kappa {kappa:.2f} (n={len(lab)}; below 0.60 = weak)")
    lab = pd.Series([a if a == b else "ambiguous" for a, b in zip(lab, r2)], index=lab.index)  # disagreement counts as ambiguous
    print("(labels below = both raters agreed; disagreements counted as ambiguous)")
r1["lab"] = r1.stim_id.map(lab)
tot_lo = tot_pt = tot_hi = tot_amb_pt = 0
print(f"\n{'source':28s} {'n':>3} {'unsuit.':>8} {'ambig.':>7} {'micro?':>7}   projected unsuitable among test photos (95% range)")
for s, n_test in TEST_N.items():
    g = r1[r1.source == s]; n = len(g); u = int((g.lab == "unsuitable").sum()); a = int((g.lab == "ambiguous").sum()); mi = int(g.notes.str.contains("micro", case=False).sum())
    lo, hi = wilson(u, n); pt = u / n * n_test if n else 0; tot_pt += pt; tot_lo += lo * n_test; tot_hi += hi * n_test; tot_amb_pt += a / n * n_test if n else 0
    print(f"{s:28s} {n:>3} {u:>8} {a:>7} {mi:>7}   {pt:5.1f}  ({lo * n_test:.0f} - {hi * n_test:.0f}) of {n_test}")
print(f"\nProjected CLEARLY unsuitable photos among the 174: about {tot_pt:.0f} (rough range {tot_lo:.0f} - {tot_hi:.0f}); ambiguous would add about {tot_amb_pt:.0f}.")
print("Rule R1 needs at least 30 consensus-unsuitable photos.")
v = "LIKELY ENOUGH" if tot_lo >= 30 else ("LIKELY UNDERPOWERED" if tot_hi < 30 or tot_pt < 24 else "UNCERTAIN - cannot tell from 36 photos")
print("Planning signal:", v, "(an estimate from 12 photos per source, not a result)")
