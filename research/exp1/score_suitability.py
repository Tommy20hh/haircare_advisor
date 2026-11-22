"""Experiment 1 - scoring. Laptop CPU only; needs pandas + numpy (matplotlib optional for the figure). Never runs a VLM.
  python research\\exp1\\score_suitability.py --make-pilot                 (after rating the dev sheet: picks ~30 dev images -> private\\pilot_ids.txt, upload with the code)
  python research\\exp1\\score_suitability.py --vlm <vlm_predictions_final_natural.csv> [--vlm-synth <..final_synth.csv>]   (final scoring)
Frozen rules are the constants below (copied from PROTOCOL). Do not edit them after the first final run."""
import argparse, json, os, sys
import numpy as np, pandas as pd
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
E1 = os.path.join(ROOT, "research", "exp1"); PRIV = os.path.join(E1, "private"); RES = os.path.join(E1, "results")
MIN_UNSUITABLE = 30; MIN_FAR_DROP = 0.10; MAX_EXTRA_FRR = 0.10; MAX_INVALID = 0.05; MAX_MEDIAN_S = 15.0; N_BOOT = 1000; SEED = 42
SCALP_SRC = {"roboflow_hairdata", "healthy_scalp", "extra_dandruff_big_chunks"}
def rd(p): return pd.read_csv(p, dtype=str).fillna("")
def kappa(a, b):
    labs = sorted(set(a) | set(b)); n = len(a); po = np.mean([x == y for x, y in zip(a, b)])
    pe = sum((sum(x == l for x in a) / n) * (sum(y == l for y in b) / n) for l in labs); return float((po - pe) / (1 - pe)) if pe < 1 else 1.0
def consensus():
    r1, r2 = rd(os.path.join(PRIV, "rating_final_rater1.csv")), rd(os.path.join(PRIV, "rating_final_rater2.csv"))
    m = r1.merge(r2, on="stim_id", suffixes=("_1", "_2")); m = m[(m.label_1 != "") & (m.label_2 != "")]
    adj = os.path.join(PRIV, "adjudication.csv"); aj = rd(adj).set_index("stim_id") if os.path.exists(adj) else pd.DataFrame(columns=["label", "failure_category"])
    lab, cat, how = [], [], []
    for _, r in m.iterrows():
        if r.stim_id in aj.index: lab.append(aj.loc[r.stim_id, "label"]); cat.append(aj.loc[r.stim_id, "failure_category"]); how.append("adjudicated")
        elif r.label_1 == r.label_2: lab.append(r.label_1); cat.append(r.failure_category_1 if r.failure_category_1 == r.failure_category_2 else (r.failure_category_1 or r.failure_category_2)); how.append("agreed")
        else: lab.append("ambiguous"); cat.append(""); how.append("unresolved->ambiguous")
    m["ref_label"], m["ref_category"], m["how"] = lab, cat, how
    k = {"kappa_3class": kappa(list(m.label_1), list(m.label_2)), "raw_agreement": float(np.mean(m.label_1 == m.label_2)), "n": int(len(m)), "adjudicated": int((m.how == "adjudicated").sum()), "unresolved": int((m.how == "unresolved->ambiguous").sum())}
    return m[["stim_id", "ref_label", "ref_category", "how"]], k
def accepts(df):
    d = pd.DataFrame({"stim_id": df.stim_id})
    d["baseline_hard"] = (df.status != "mismatch").astype(int); d["baseline_strict"] = (df.status == "match").astype(int)
    d["vlm"] = ((df.valid_json == "1") & (df.suitable == "yes")).astype(int)
    d["combined_hard"] = d.baseline_hard & d.vlm; d["combined_strict"] = d.baseline_strict & d.vlm; return d
def rates(d, systems):
    U, S = d[d.ref_label == "unsuitable"], d[d.ref_label == "suitable"]; out = {}
    for s in systems:
        rej = d[(d[s] == 0) & d.ref_label.isin(["suitable", "unsuitable"])]
        out[s] = {"FAR": float(U[s].mean()) if len(U) else np.nan, "FRR": float(1 - S[s].mean()) if len(S) else np.nan,
                  "recall_unsuitable_rejected": float(1 - U[s].mean()) if len(U) else np.nan, "precision_of_rejections": float((rej.ref_label == "unsuitable").mean()) if len(rej) else np.nan,
                  "coverage_accepted": float(d[d.ref_label.isin(["suitable", "unsuitable"])][s].mean()) if len(d) else np.nan, "n_unsuitable": int(len(U)), "n_suitable": int(len(S))}
    return out
def boot(d, fn, rng):
    cl = d.groupby("cluster").indices; keys = list(cl); vals = []
    for _ in range(N_BOOT):
        pick = rng.choice(len(keys), len(keys)); idx = np.concatenate([cl[keys[i]] for i in pick]); vals.append(fn(d.iloc[idx]))
    v = np.array(vals, dtype=float); return [float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))] if np.isfinite(v).any() else [np.nan, np.nan]
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--make-pilot", action="store_true"); ap.add_argument("--vlm"); ap.add_argument("--vlm-synth"); ap.add_argument("--score-pilot", help="vlm_predictions_dev.csv from the Kaggle pilot"); ap.add_argument("--baseline", default=os.path.join(RES, "baseline_predictions.csv")); a = ap.parse_args()
    pm = rd(os.path.join(PRIV, "manifest_private.csv")); os.makedirs(RES, exist_ok=True)
    if a.score_pilot:
        pv = rd(a.score_pilot); dv = rd(os.path.join(PRIV, "rating_dev_rater1.csv")); dv = dv[dv.label != ""][["stim_id", "label", "failure_category"]]
        sy = pm[pm.kind.str.startswith("synthetic")][["stim_id", "expected_label", "expected_category"]].rename(columns={"expected_label": "label", "expected_category": "failure_category"})
        j = pv.merge(pd.concat([dv, sy]), on="stim_id", suffixes=("_vlm", "_ref")); j["vlm_accept"] = ((j.valid_json == "1") & (j["suitable"] == "yes")).astype(int)
        U, S, A = j[j.label == "unsuitable"], j[j.label == "suitable"], j[j.label == "ambiguous"]
        r = {"n": int(len(j)), "valid_json_rate": float((j.valid_json == "1").mean()), "accuracy_accept_vs_reject_on_suitable_unsuitable": float(np.mean(list(S.vlm_accept == 1) + list(U.vlm_accept == 0))) if len(S) + len(U) else None,
             "suitable_accepted": f"{int(S.vlm_accept.sum())}/{len(S)}", "unsuitable_rejected": f"{int((U.vlm_accept == 0).sum())}/{len(U)}", "ambiguous_accepted": f"{int(A.vlm_accept.sum())}/{len(A)}",
             "failure_category_match_on_unsuitable": float((U.failure_category_vlm == U.failure_category_ref).mean()) if len(U) else None, "median_latency_s": float(pd.to_numeric(j.latency_s, errors="coerce").median())}
        os.makedirs(RES, exist_ok=True); json.dump(r, open(os.path.join(RES, "pilot_summary.json"), "w"), indent=2); print(json.dumps(r, indent=2)); return
    if a.make_pilot:
        dv = rd(os.path.join(PRIV, "rating_dev_rater1.csv")); dv = dv[dv.label != ""].merge(pm[["stim_id", "source"]], on="stim_id")
        rng = np.random.default_rng(SEED); pick = []
        for lab, n in (("suitable", 9), ("unsuitable", 9), ("ambiguous", 4)):
            g = dv[dv.label == lab]; pick += list(g.stim_id.iloc[rng.permutation(len(g))[:n]])
        syn = pm[(pm["set"] == "dev") & pm.kind.str.startswith("synthetic")]; pick += list(syn.stim_id.iloc[rng.permutation(len(syn))[:8]])
        open(os.path.join(PRIV, "pilot_ids.txt"), "w").write("\n".join(pick) + "\n"); print("pilot images:", len(pick), "| ambiguous available:", int((dv.label == "ambiguous").sum()), "(pilot should contain >=3)"); return
    ref, kap = consensus(); base = rd(a.baseline); vlm = rd(a.vlm)
    if a.vlm_synth: vlm = pd.concat([vlm, rd(a.vlm_synth)])
    pred = accepts(base.merge(vlm[["stim_id", "valid_json", "suitable", "failure_category", "latency_s"]], on="stim_id", how="inner"))
    nat = pred.merge(ref, on="stim_id").merge(pm[["stim_id", "source", "original_id"]], on="stim_id"); nat["cluster"] = nat.original_id
    systems = ["baseline_hard", "baseline_strict", "vlm", "combined_hard", "combined_strict"]; rng = np.random.default_rng(SEED); res = {"agreement": kap, "pre_registered": {"min_unsuitable": MIN_UNSUITABLE, "far_drop": MIN_FAR_DROP, "extra_frr": MAX_EXTRA_FRR, "invalid": MAX_INVALID, "median_s": MAX_MEDIAN_S}}
    subsets = {"all_natural": nat, "scalp_sources_only": nat[nat.source.isin(SCALP_SRC)], "faces_only_easy_check": nat[nat.source == "kaggle_balding"]}
    for s in sorted(nat.source.unique()): subsets["source:" + s] = nat[nat.source == s]
    for c in sorted(set(nat[nat.ref_label == "unsuitable"].ref_category) - {""}): subsets["category:" + c] = nat[(nat.ref_label == "unsuitable") & (nat.ref_category == c) | (nat.ref_label == "suitable")]
    res["natural"] = {k: rates(v, systems) for k, v in subsets.items() if len(v)}
    amb = nat[nat.ref_label == "ambiguous"]; res["ambiguous_accept_rate"] = {s: (float(amb[s].mean()) if len(amb) else None) for s in systems}; res["n_ambiguous"] = int(len(amb))
    sc = subsets["scalp_sources_only"]; ci = {}
    for b in ("hard", "strict"):
        far_d = lambda d, b=b: rates(d, ["baseline_" + b, "combined_" + b])["combined_" + b]["FAR"] - rates(d, ["baseline_" + b, "combined_" + b])["baseline_" + b]["FAR"]
        frr_d = lambda d, b=b: rates(d, ["baseline_" + b, "combined_" + b])["combined_" + b]["FRR"] - rates(d, ["baseline_" + b, "combined_" + b])["baseline_" + b]["FRR"]
        ci[b] = {"far_diff": far_d(sc), "far_diff_ci95": boot(sc, far_d, rng), "frr_diff": frr_d(sc), "frr_diff_ci95": boot(sc, frr_d, rng)}
    res["paired_scalp_only"] = ci
    lat = pd.to_numeric(vlm.latency_s, errors="coerce"); inv = float((vlm.valid_json != "1").mean()); med = float(lat.median()) if lat.notna().any() else None
    nU = int((sc.ref_label == "unsuitable").sum()); rules = {}
    for b in ("hard", "strict"):
        c = ci[b]; rules[b] = {"R1_enough_unsuitable_scalp_photos": nU >= MIN_UNSUITABLE, "R2_far_drop_ge_10pp_and_ci_excludes_0": bool(c["far_diff"] <= -MIN_FAR_DROP and c["far_diff_ci95"][1] < 0) if nU else False,
                               "R3_extra_frr_le_10pp": bool(c["frr_diff"] <= MAX_EXTRA_FRR) if np.isfinite(c["frr_diff"]) else False, "R4_invalid_le_5pct_and_median_le_15s": bool(inv <= MAX_INVALID and med is not None and med <= MAX_MEDIAN_S)}
        rules[b]["verdict"] = ("UNDERPOWERED/EXPLORATORY - no adoption decision" if nU < MIN_UNSUITABLE else ("PASS (laboratory result only)" if all(v for k, v in rules[b].items() if k.startswith("R")) else "FAIL - stop VLM line"))
    res["invalid_json_rate"], res["median_latency_s"], res["decision_rules"] = inv, med, rules
    syn = pred.merge(pm[["stim_id", "variant_type", "severity", "original_id", "kind", "set"]], on="stim_id"); syn = syn[syn["set"] == "final_synth"]
    if len(syn):
        syn["cluster"] = syn.original_id; res["synthetic_reject_rate_by_type_severity"] = {f"{t}/{s}": {sy: float(1 - g[sy].mean()) for sy in systems} | {"n": int(len(g)), "n_originals": int(g.cluster.nunique())} for (t, s), g in syn.groupby(["variant_type", "severity"])}
    json.dump(res, open(os.path.join(RES, "metrics.json"), "w"), indent=2, default=str); nat.to_csv(os.path.join(RES, "per_image_joined.csv"), index=False)
    pd.DataFrame([{"subset": k, "system": s, **m} for k, v in res["natural"].items() for s, m in v.items()]).to_csv(os.path.join(RES, "table_natural_by_subset.csv"), index=False)
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        t = res["natural"].get("scalp_sources_only", {}); x = np.arange(len(systems)); fig, ax = plt.subplots(figsize=(7, 3.5))
        ax.bar(x - 0.2, [t.get(s, {}).get("FAR", np.nan) for s in systems], 0.4, label="False acceptance"); ax.bar(x + 0.2, [t.get(s, {}).get("FRR", np.nan) for s in systems], 0.4, label="False rejection")
        ax.set_xticks(x); ax.set_xticklabels(systems, rotation=20); ax.set_ylim(0, 1); ax.legend(); ax.set_title("Scalp-source natural photos"); fig.tight_layout(); fig.savefig(os.path.join(RES, "fig_far_frr.png"), dpi=200)
    except Exception as e: print("figure skipped:", e)
    print(json.dumps({k: res[k] for k in ("agreement", "decision_rules", "invalid_json_rate", "median_latency_s")}, indent=1, default=str))
if __name__ == "__main__": main()
