"""
Honest evaluation of ONE task's trained bundle on its held-out test rows.

    python src/evaluate.py --task scalp --labels data/scalp_labels.csv \
        --img-dir RAW_ROOT --checkpoint checkpoints/scalp_model.pt --results-dir results/scalp

Reports, per condition (only on images that were really labelled for it):
precision / recall / F1 / specificity at the tuned threshold, AUROC and average
precision with 95% bootstrap confidence intervals, calibration error (ECE),
a majority-class baseline, and how often the model answers "inconclusive".
Also writes confusion matrices, PR curves and a reliability diagram.
"""

import argparse
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
from sklearn.metrics import average_precision_score, confusion_matrix, precision_recall_curve, roc_auc_score
from torch.utils.data import DataLoader

from calibration import sigmoid
from dataset import ConditionDataset, EVAL_TRANSFORM, read_labels
from inference import calibrated_probs, ensemble_logits, load_bundle
from model import TASKS


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--task", required=True, choices=list(TASKS))
    p.add_argument("--labels", required=True)
    p.add_argument("--img-dir", required=True)
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--results-dir", default="results")
    p.add_argument("--split", default="test")
    p.add_argument("--only-source", default=None,
                   help="Evaluate only images from this source (e.g. roboflow_hairdata). This removes the photo-style shortcut.")
    p.add_argument("--bootstrap", type=int, default=1000)
    p.add_argument("--num-workers", type=int, default=2)
    return p.parse_args()


def bootstrap_ci(y, p, pred, n, seed=0, groups=None):
    """95% bootstrap interval. If `groups` is given, whole groups of near-identical photos
    are resampled together, so duplicates are not counted as independent evidence."""
    rng = np.random.default_rng(seed)
    if groups is None:
        groups = np.arange(len(y))
    uniq = np.unique(groups)
    members = {g: np.nonzero(groups == g)[0] for g in uniq}
    aucs, f1s = [], []
    for _ in range(n):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        ix = np.concatenate([members[g] for g in pick])
        yy, pp, pr = y[ix], p[ix], pred[ix]
        if yy.sum() == 0 or yy.sum() == len(yy):
            continue
        aucs.append(roc_auc_score(yy, pp))
        tp = ((yy == 1) & (pr == 1)).sum(); fp = ((yy == 0) & (pr == 1)).sum(); fn = ((yy == 1) & (pr == 0)).sum()
        f1s.append(2 * tp / max(2 * tp + fp + fn, 1))
    ci = lambda v: [round(float(np.percentile(v, 2.5)), 3), round(float(np.percentile(v, 97.5)), 3)] if v else None
    return ci(aucs), ci(f1s)


def ece(y, p, bins=10):
    edges = np.linspace(0, 1, bins + 1)
    total, err = len(y), 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        sel = (p >= lo) & (p < hi if hi < 1 else p <= hi)
        if sel.any():
            err += sel.sum() / total * abs(y[sel].mean() - p[sel].mean())
    return float(err)


def main():
    args = parse_args()
    classes = TASKS[args.task]
    os.makedirs(args.results_dir, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    bundle = load_bundle(args.checkpoint, device)
    if bundle is None:
        raise FileNotFoundError(args.checkpoint)
    df = read_labels(args.labels, classes)
    df = df[df["split"] == args.split]
    if args.only_source:
        df = df[df["source"] == args.only_source]
    df = df.reset_index(drop=True)
    if df.empty:
        raise SystemExit(f"No rows with split == {args.split!r} in {args.labels}")
    ds = ConditionDataset(df, args.img_dir, classes, EVAL_TRANSFORM)
    loader = DataLoader(ds, batch_size=32, shuffle=False, num_workers=args.num_workers)

    logits = np.concatenate([ensemble_logits(bundle, x) for x, _, _ in loader])
    probs = calibrated_probs(bundle, logits)
    raw_probs = sigmoid(logits)
    labels, mask = ds.labels, ds.mask

    lines, results = [], {}
    lines.append(f"TASK: {args.task} | test images: {len(df)}{' (only source: ' + args.only_source + ')' if args.only_source else ''} | ensemble size: {len(bundle.models)} "
                 f"| temperature: {bundle.temperature:.2f}")
    lines.append(f"Decision thresholds (tuned on out-of-fold data): {bundle.thresholds}; inconclusive band +-{bundle.band}")
    lines.append("")
    fig_cm, axes_cm = plt.subplots(1, len(classes), figsize=(4.2 * len(classes), 3.8), squeeze=False)
    fig_pr, ax_pr = plt.subplots(figsize=(5, 4))
    fig_rel, ax_rel = plt.subplots(figsize=(4.5, 4.5))
    ax_rel.plot([0, 1], [0, 1], "k--", lw=1, label="perfect")

    for i, name in enumerate(classes):
        m = mask[:, i] == 1
        y, p, rp = labels[m, i].astype(int), probs[m, i], raw_probs[m, i]
        t = bundle.thresholds[name]
        pred = (p >= t).astype(int)
        base = np.full_like(y, int(y.mean() >= 0.5))
        tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
        prec, rec = tp / max(tp + fp, 1), tp / max(tp + fn, 1)
        f1 = 2 * tp / max(2 * tp + fp + fn, 1)
        spec = tn / max(tn + fp, 1)
        has_both = 0 < y.sum() < len(y)
        auroc = float(roc_auc_score(y, p)) if has_both else None
        ap = float(average_precision_score(y, p)) if has_both else None
        grp = df['group'].to_numpy()[m] if 'group' in df.columns else None
        auc_ci, f1_ci = bootstrap_ci(y, p, pred, args.bootstrap, groups=grp) if has_both else (None, None)
        inconc = float(((p > t - bundle.band) & (p < t + bundle.band)).mean())
        sure = ~((p > t - bundle.band) & (p < t + bundle.band))
        sure_acc = float((pred[sure] == y[sure]).mean()) if sure.any() else None
        results[name] = {
            "n_tested": int(m.sum()), "n_positive": int(y.sum()), "threshold": t,
            "precision": round(prec, 3), "recall": round(rec, 3), "f1": round(f1, 3), "specificity": round(spec, 3),
            "auroc": None if auroc is None else round(auroc, 3), "auroc_95ci": auc_ci, "f1_95ci": f1_ci,
            "average_precision": None if ap is None else round(ap, 3),
            "accuracy": round(float((pred == y).mean()), 3), "baseline_accuracy": round(float((base == y).mean()), 3),
            "ece_calibrated": round(ece(y, p), 3), "ece_uncalibrated": round(ece(y, rp), 3),
            "inconclusive_rate": round(inconc, 3),
            "accuracy_when_conclusive": None if sure_acc is None else round(sure_acc, 3),
            "tn_fp_fn_tp": [int(tn), int(fp), int(fn), int(tp)],
        }
        r = results[name]
        # AUROC inside each photo source separately: only counts where that source has BOTH positives and
        # negatives, so the model cannot win by recognising which dataset a photo came from.
        within = {}
        srcs = df["source"].to_numpy()[m]
        for src in np.unique(srcs):
            sel = srcs == src
            if y[sel].sum() >= 5 and (1 - y[sel]).sum() >= 5:
                g_sel = grp[sel] if grp is not None else None
                ci_s, _ = bootstrap_ci(y[sel], p[sel], pred[sel], args.bootstrap, groups=g_sel)
                within[str(src)] = {"auroc": round(float(roc_auc_score(y[sel], p[sel])), 3), "auroc_95ci": ci_s,
                                    "n": int(sel.sum()), "n_pos": int(y[sel].sum())}
        results[name]["within_source_auroc"] = within
        lines += [
            f"[{name}]  tested on {r['n_tested']} images ({r['n_positive']} positive)",
            f"  precision {r['precision']}  recall {r['recall']}  F1 {r['f1']} (95% CI {r['f1_95ci']})  specificity {r['specificity']}",
            f"  AUROC {r['auroc']} (95% CI {r['auroc_95ci']})  average precision {r['average_precision']}",
            f"  accuracy {r['accuracy']} vs always-majority baseline {r['baseline_accuracy']}",
            f"  calibration error (ECE): {r['ece_uncalibrated']} before -> {r['ece_calibrated']} after calibration",
            f"  says 'inconclusive' on {r['inconclusive_rate']:.0%} of photos; accuracy on the rest: {r['accuracy_when_conclusive']}",
            ("  style-free check (AUROC inside one photo source): " + (", ".join(f"{k} {v['auroc']} (95% CI {v['auroc_95ci']}, n={v['n']}, {v['n_pos']} pos)" for k, v in within.items()) or "NOT AVAILABLE: no single source has >=5 positives and >=5 negatives")),
            "",
        ]
        sns_cm = np.array([[tn, fp], [fn, tp]])
        ax = axes_cm[0][i]
        ax.imshow(sns_cm, cmap="Blues")
        for (a, b), v in np.ndenumerate(sns_cm):
            ax.text(b, a, str(v), ha="center", va="center", color="white" if v > sns_cm.max() / 2 else "black")
        ax.set_xticks([0, 1], ["Absent", "Present"]); ax.set_yticks([0, 1], ["Absent", "Present"])
        ax.set_title(name); ax.set_xlabel("Predicted"); ax.set_ylabel("Actual")
        if has_both:
            pr, rc, _ = precision_recall_curve(y, p)
            ax_pr.plot(rc, pr, label=f"{name} (AP {ap:.2f})")
            bins = np.linspace(0, 1, 6)
            xs, ys = [], []
            for lo, hi in zip(bins[:-1], bins[1:]):
                sel = (p >= lo) & (p <= hi)
                if sel.sum() >= 3:
                    xs.append(p[sel].mean()); ys.append(y[sel].mean())
            ax_rel.plot(xs, ys, "o-", label=name)

    # Does the model just recognise which dataset a photo came from?
    if df["source"].nunique() > 1:
        lines.append("Average predicted probability by image source (large gaps can mean the model keys on photo style):")
        for src, grp in df.groupby("source"):
            ix = grp.index.to_numpy()
            lines.append(f"  {src:<22} n={len(ix):<4} " + "  ".join(f"{c}={probs[ix, j].mean():.2f}" for j, c in enumerate(classes)))
        lines.append("")

    ax_pr.set_xlabel("Recall"); ax_pr.set_ylabel("Precision"); ax_pr.set_title("Precision-recall"); ax_pr.legend()
    ax_rel.set_xlabel("Predicted probability"); ax_rel.set_ylabel("Observed frequency"); ax_rel.set_title("Reliability"); ax_rel.legend()
    fig_cm.tight_layout(); fig_pr.tight_layout(); fig_rel.tight_layout()
    fig_cm.savefig(os.path.join(args.results_dir, "confusion_matrices.png"), dpi=150)
    fig_pr.savefig(os.path.join(args.results_dir, "pr_curves.png"), dpi=150)
    fig_rel.savefig(os.path.join(args.results_dir, "reliability.png"), dpi=150)

    text = "\n".join(lines)
    print(text)
    with open(os.path.join(args.results_dir, "report.txt"), "w") as fh:
        fh.write(text)
    with open(os.path.join(args.results_dir, "metrics.json"), "w") as fh:
        json.dump(results, fh, indent=2)
    print(f"Saved report, metrics.json and figures to {args.results_dir}")


if __name__ == "__main__":
    main()
