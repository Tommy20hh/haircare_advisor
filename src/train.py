"""
Trains ONE task's classifier (balding OR scalp) to a high standard.

    python src/train.py --task balding --labels data/balding_labels.csv --img-dir RAW_ROOT
    python src/train.py --task scalp   --labels data/scalp_labels.csv   --img-dir RAW_ROOT

What it does (and why):
  * Transfer learning with MobileNetV2, trained in two stages: first only the new
    head (backbone frozen), then the whole network at a lower learning rate.
    This protects the pretrained features when the dataset is small.
  * Strong augmentation (dataset.py) so the model doesn't memorise photo style.
  * Masked loss: a condition the source dataset never labelled is UNKNOWN and is
    skipped, never counted as "absent".
  * K-fold cross-validation (default 5 for scalp). With a few hundred images a
    single split is too noisy to trust. The K fold models are kept and used as
    an ENSEMBLE at prediction time.
  * Calibration + per-condition thresholds are fitted on the out-of-fold
    predictions, so reported confidences mean what they say.
  * The rows with split == "test" are never read here.
"""

import argparse
import copy
import json
import os
import random

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold, train_test_split
from torch import optim
from torch.utils.data import DataLoader, WeightedRandomSampler
import torch.nn.functional as F

from calibration import fit_temperature, masked_nll, sigmoid, tune_thresholds
from dataset import ConditionDataset, TRAIN_TRANSFORM, STRONG_TRAIN_TRANSFORM, EVAL_TRANSFORM, read_labels
from model import TASKS, build_model, grad_reverse

TASK_DEFAULTS = {
    "balding": {"epochs": 12, "warmup": 2, "folds": 1},
    "scalp": {"epochs": 30, "warmup": 4, "folds": 5},
}


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--task", required=True, choices=list(TASKS))
    p.add_argument("--labels", required=True, help="Path to <task>_labels.csv")
    p.add_argument("--img-dir", required=True, help="Folder the filepaths in the CSV are relative to")
    p.add_argument("--out-dir", default="checkpoints")
    p.add_argument("--epochs", type=int, default=None)
    p.add_argument("--warmup-epochs", type=int, default=None, help="Epochs with the backbone frozen")
    p.add_argument("--folds", type=int, default=None, help="K-fold CV (1 = single train/val split)")
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--lr", type=float, default=1e-3, help="Head learning rate")
    p.add_argument("--backbone-lr", type=float, default=1e-4)
    p.add_argument("--pos-weight-cap", type=float, default=5.0,
                   help="Max loss weight on rare positives (mild on purpose; calibration handles the rest)")
    p.add_argument("--patience", type=int, default=7)
    p.add_argument("--uncertain-band", type=float, default=0.10)
    p.add_argument("--val-fraction", type=float, default=0.15, help="Only used when --folds 1 and no val split exists")
    p.add_argument("--num-workers", type=int, default=2)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--aug", choices=["standard", "strong"], default="standard",
                   help="strong = also randomises colour, grayscale, JPEG quality, resolution, noise (reduces photo-style shortcuts)")
    p.add_argument("--balance-sources", action="store_true",
                   help="Draw training batches so each photo source contributes equally (small sources are not drowned out)")
    p.add_argument("--source-adv", type=float, default=0.0,
                   help="Source-blind training weight (0 = off). >0 adds a 'which source is this photo from?' guesser whose "
                        "gradient is reversed, pushing the features to carry no source information")
    p.add_argument("--no-pretrained", action="store_true", help="Smoke tests only (skips weight download)")
    return p.parse_args()


def seed_everything(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def masked_bce(logits, targets, mask, pos_weight=None):
    loss = F.binary_cross_entropy_with_logits(logits, targets, pos_weight=pos_weight, reduction="none")
    return (loss * mask).sum() / mask.sum().clamp(min=1.0)


def compute_pos_weight(df, class_names, cap, device):
    raw = df[class_names].to_numpy(dtype=np.float32)
    mask = ~np.isnan(raw)
    weights = []
    for i in range(len(class_names)):
        col = raw[mask[:, i], i]
        pos, neg = float((col == 1).sum()), float((col == 0).sum())
        weights.append(float(np.clip(neg / max(pos, 1.0), 1.0, cap)))
    return torch.tensor(weights, dtype=torch.float32, device=device)


@torch.no_grad()
def collect_logits(model, loader, device):
    model.eval()
    all_l, all_y, all_m = [], [], []
    for x, y, m in loader:
        all_l.append(model(x.to(device)).cpu().numpy())
        all_y.append(y.numpy())
        all_m.append(m.numpy())
    return np.concatenate(all_l), np.concatenate(all_y), np.concatenate(all_m)


def train_one_model(train_df, val_df, args, classes, device, tag):
    sources = sorted(train_df["source"].unique())
    use_adv = args.source_adv > 0 and len(sources) > 1
    src_idx = {s_: i for i, s_ in enumerate(sources)}
    transform = STRONG_TRAIN_TRANSFORM if args.aug == "strong" else TRAIN_TRANSFORM
    train_ds = ConditionDataset(train_df, args.img_dir, classes, transform, source_to_idx=src_idx if use_adv else None)
    val_ds = ConditionDataset(val_df, args.img_dir, classes, EVAL_TRANSFORM)
    pin = device.type == "cuda"
    sampler = None
    if args.balance_sources and len(sources) > 1:
        counts = train_df["source"].value_counts()
        w = train_df["source"].map(lambda s_: 1.0 / counts[s_]).to_numpy()
        sampler = WeightedRandomSampler(torch.tensor(w, dtype=torch.double), num_samples=len(train_df), replacement=True)
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=sampler is None, sampler=sampler,
                              num_workers=args.num_workers, pin_memory=pin, drop_last=len(train_ds) > args.batch_size)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False,
                            num_workers=args.num_workers, pin_memory=pin)

    pos_weight = compute_pos_weight(train_df, classes, args.pos_weight_cap, device)
    model = build_model(args.task, pretrained=not args.no_pretrained).to(device)
    dom_head = torch.nn.Linear(1280, len(sources)).to(device) if use_adv else None
    scaler = torch.amp.GradScaler("cuda", enabled=pin)

    best = {"loss": float("inf"), "state": None, "epoch": 0}
    bad_epochs = 0
    optimizer = scheduler = None

    for epoch in range(1, args.epochs + 1):
        frozen = epoch <= args.warmup_epochs
        if epoch == 1 or epoch == args.warmup_epochs + 1:
            model.set_backbone_frozen(frozen)
            if frozen:
                optimizer = optim.AdamW(model.backbone.classifier.parameters(), lr=args.lr, weight_decay=1e-4)
                scheduler = None
                dom_opt = optim.AdamW(dom_head.parameters(), lr=args.lr) if use_adv else None
            else:
                optimizer = optim.AdamW([
                    {"params": model.backbone.features.parameters(), "lr": args.backbone_lr},
                    {"params": model.backbone.classifier.parameters(), "lr": args.lr / 3},
                ], weight_decay=1e-4)
                dom_opt = optim.AdamW(dom_head.parameters(), lr=args.lr) if use_adv else None
                scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max(args.epochs - args.warmup_epochs, 1))

        model.train()
        if frozen:
            model.backbone.features.eval()  # keep BatchNorm statistics of the pretrained net

        total, n = 0.0, 0
        for batch in train_loader:
            x, y, m = (t.to(device) for t in batch[:3])
            optimizer.zero_grad(set_to_none=True)
            if dom_opt is not None:
                dom_opt.zero_grad(set_to_none=True)
            with torch.autocast(device_type=device.type, enabled=pin):
                if use_adv and not frozen:
                    pooled = model.pooled(x)
                    logits = model.head(pooled)
                    # ramp the reversal strength 0 -> args.source_adv over the unfrozen epochs
                    prog = (epoch - args.warmup_epochs - 1) / max(args.epochs - args.warmup_epochs, 1)
                    lam = float(args.source_adv * (2.0 / (1.0 + np.exp(-10 * prog)) - 1.0))
                    dom_logits = dom_head(grad_reverse(pooled, lam))
                else:
                    logits = model(x)
                    dom_logits = None
            loss = masked_bce(logits.float(), y, m, pos_weight)
            if dom_logits is not None:
                loss = loss + F.cross_entropy(dom_logits.float(), batch[3].to(device))
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            if dom_opt is not None and use_adv and not frozen:
                scaler.step(dom_opt)
            scaler.update()
            total += loss.item() * x.size(0)
            n += x.size(0)
        if scheduler is not None:
            scheduler.step()

        logits_v, y_v, m_v = collect_logits(model, val_loader, device)
        val_loss = masked_nll(logits_v, y_v, m_v, 1.0)  # unweighted log-loss: honest, comparable
        print(f"  [{tag}] epoch {epoch:>2}/{args.epochs} {'(head only)' if frozen else '           '} "
              f"train_loss={total / max(n, 1):.4f} val_logloss={val_loss:.4f}")

        if val_loss < best["loss"] - 1e-4:
            best = {"loss": val_loss, "state": copy.deepcopy(model.state_dict()), "epoch": epoch}
            bad_epochs = 0
        elif not frozen:
            bad_epochs += 1
            if bad_epochs >= args.patience:
                print(f"  [{tag}] early stop (no improvement for {args.patience} epochs)")
                break

    model.load_state_dict(best["state"])
    logits_v, y_v, m_v = collect_logits(model, val_loader, device)
    state_cpu = {k: v.cpu() for k, v in best["state"].items()}
    return state_cpu, logits_v, y_v, m_v, best


def make_folds(df, classes, k, seed):
    raw = df[classes].to_numpy(dtype=np.float32)
    keys = np.array(["".join("?" if np.isnan(v) else str(int(v)) for v in row) + "|" + str(src)
                     for row, src in zip(raw, df["source"])])
    counts = pd.Series(keys).value_counts()
    rare = set(counts[counts < k].index)
    keys = np.array(["rare" if kk in rare else kk for kk in keys])
    if (keys == "rare").sum() < k and (keys == "rare").sum() > 0:
        keys[keys == "rare"] = counts.index[0] if counts.index[0] not in rare else keys[keys != "rare"][0]
    if "group" in df.columns:  # near-duplicate photos stay together -> leak-free folds
        sgkf = StratifiedGroupKFold(n_splits=k, shuffle=True, random_state=seed)
        return list(sgkf.split(np.zeros(len(df)), keys, groups=df["group"].to_numpy()))
    skf = StratifiedKFold(n_splits=k, shuffle=True, random_state=seed)
    return list(skf.split(np.zeros(len(df)), keys))


def within_source_auroc(probs, labels, mask, classes, sources):
    """AUROC computed INSIDE each photo source that has both positives and negatives.
    This is the style-free number: the model cannot win by recognising the source."""
    out = {}
    for i, name in enumerate(classes):
        out[name] = {}
        for src in np.unique(sources):
            sel = (sources == src) & (mask[:, i] == 1)
            y, p = labels[sel, i], probs[sel, i]
            if y.sum() >= 5 and (1 - y).sum() >= 5:
                out[name][str(src)] = {"auroc": round(float(roc_auc_score(y, p)), 4), "n": int(sel.sum()), "n_pos": int(y.sum())}
    return out


def per_class_metrics(probs, labels, mask, classes):
    out = {}
    for i, name in enumerate(classes):
        m = mask[:, i] == 1
        y, p = labels[m, i], probs[m, i]
        entry = {"n_labelled": int(m.sum()), "n_positive": int(y.sum())}
        if 0 < y.sum() < len(y):
            entry["auroc"] = round(float(roc_auc_score(y, p)), 4)
        out[name] = entry
    return out


def main():
    args = parse_args()
    d = TASK_DEFAULTS[args.task]
    args.epochs = args.epochs or d["epochs"]
    args.warmup_epochs = d["warmup"] if args.warmup_epochs is None else args.warmup_epochs
    args.folds = d["folds"] if args.folds is None else args.folds
    seed_everything(args.seed)

    classes = TASKS[args.task]
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Task: {args.task} {classes} | device: {device} | epochs: {args.epochs} "
          f"(first {args.warmup_epochs} head-only) | folds: {args.folds}")

    df = read_labels(args.labels, classes)
    pool = df[df["split"].isin(["train", "val"])].reset_index(drop=True)  # test rows never touched
    print(f"Training pool: {len(pool)} images (held-out test rows excluded: {(df['split'] == 'test').sum()})")
    for c in classes:
        col = pool[c].dropna()
        print(f"  {c}: {int((col == 1).sum())} positive / {int((col == 0).sum())} negative / {int(pool[c].isna().sum())} unknown")
    print("  sources:", pool["source"].value_counts().to_dict())

    states, oof_logits, oof_y, oof_m, oof_idx, fold_info = [], [], [], [], [], []
    if args.folds > 1:
        for f, (tr, va) in enumerate(make_folds(pool, classes, args.folds, args.seed), 1):
            print(f"Fold {f}/{args.folds}: train {len(tr)} / val {len(va)}")
            st, lg, y, m, best = train_one_model(pool.iloc[tr], pool.iloc[va], args, classes, device, f"fold{f}")
            states.append(st); oof_logits.append(lg); oof_y.append(y); oof_m.append(m); oof_idx.append(va)
            fold_info.append({"fold": f, "best_epoch": best["epoch"], "val_logloss": round(best["loss"], 4)})
    else:
        if (pool["split"] == "val").any():
            tr_df, va_df = pool[pool["split"] == "train"], pool[pool["split"] == "val"]
        else:
            tr_df, va_df = train_test_split(pool, test_size=args.val_fraction, random_state=args.seed)
        print(f"Single split: train {len(tr_df)} / val {len(va_df)}")
        st, lg, y, m, best = train_one_model(tr_df, va_df, args, classes, device, "model")
        states.append(st); oof_logits.append(lg); oof_y.append(y); oof_m.append(m)
        oof_idx.append(va_df.index.to_numpy())
        fold_info.append({"fold": 1, "best_epoch": best["epoch"], "val_logloss": round(best["loss"], 4)})

    logits = np.concatenate(oof_logits); y = np.concatenate(oof_y); m = np.concatenate(oof_m)
    idx = np.concatenate(oof_idx)

    raw_probs = sigmoid(logits)
    temperature = fit_temperature(logits, y, m)
    probs = sigmoid(logits / temperature)
    thresholds = tune_thresholds(probs, y, m, classes)
    nll_before, nll_after = masked_nll(logits, y, m, 1.0), masked_nll(logits, y, m, temperature)

    metrics = per_class_metrics(probs, y, m, classes)
    oof_sources = pool.iloc[idx]["source"].to_numpy()
    style_free = within_source_auroc(probs, y, m, classes, oof_sources)
    print("\n=== Out-of-fold results (every image predicted by a model that never trained on it) ===")
    print(f"Temperature: {temperature:.2f}  (log-loss {nll_before:.4f} -> {nll_after:.4f} after calibration)")
    for name in classes:
        print(f"  {name}: AUROC={metrics[name].get('auroc', 'n/a')} threshold={thresholds[name]} "
              f"(positives: {metrics[name]['n_positive']})")
        for src, v in style_free[name].items():
            print(f"      style-free (inside {src}): AUROC={v['auroc']}  n={v['n']} positives={v['n_pos']}")

    os.makedirs(args.out_dir, exist_ok=True)
    ckpt_path = os.path.join(args.out_dir, f"{args.task}_model.pt")
    torch.save({
        "task": args.task,
        "class_names": classes,
        "state_dicts": states,
        "temperature": temperature,
        "thresholds": thresholds,
        "uncertain_band": args.uncertain_band,
        "cv_metrics": {"per_class": metrics, "style_free": style_free, "folds": fold_info,
                       "logloss_before_calibration": round(nll_before, 4),
                       "logloss_after_calibration": round(nll_after, 4)},
        "args": vars(args),
        "n_train": int(len(pool)),
    }, ckpt_path)

    oof = pool.iloc[idx][["filepath", "source"]].copy().reset_index(drop=True)
    for i, c in enumerate(classes):
        oof[f"{c}_true"] = np.where(m[:, i] == 1, y[:, i], np.nan)
        oof[f"{c}_prob"] = probs[:, i]
    oof.to_csv(os.path.join(args.out_dir, f"{args.task}_oof_predictions.csv"), index=False)
    with open(os.path.join(args.out_dir, f"{args.task}_training_summary.json"), "w") as fh:
        json.dump({"temperature": temperature, "thresholds": thresholds, "metrics": metrics,
                   "style_free_oof": style_free, "folds": fold_info, "args": vars(args)}, fh, indent=2)
    print(f"\nSaved {ckpt_path} ({len(states)} model(s) in the ensemble)")


if __name__ == "__main__":
    main()
