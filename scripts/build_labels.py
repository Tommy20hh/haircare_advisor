"""
Builds the TWO label files, one per model, from the raw downloads.
Nothing is filled in across datasets: each model only sees data that was
really labelled for it.

    python scripts/build_labels.py --raw-root /path/to/raw --out-dir data

Expected layout under --raw-root (the balding and dryness_dandruff folders are
required, the other two are optional but strongly recommended):

  balding/Dataset/{Train,Validation,Test}/{Bald,NotBald}/*.jpg      Kaggle (face photos)
  dryness_dandruff/{train,valid,test}/_annotations.coco.json + imgs Roboflow "hairdata"
  extra_scalp/<any-name>/{train,valid,test}/_annotations.coco.json  more Roboflow sets (e.g. dandruff-big-chunks)
  healthy_scalp/**/*.jpg                                            Roboflow "healthy-scalp" images

Writes:
  <out-dir>/balding_labels.csv : filepath,balding,split,source
  <out-dir>/scalp_labels.csv   : filepath,dryness,dandruff,low_density,split,source

Rules that keep the labels honest
  * A condition a dataset never annotated is left EMPTY (unknown), not 0.
  * Healthy-scalp photos are confirmed negatives for all three conditions.
  * A scalp image whose ONLY annotations are other conditions (alopecia, psoriasis,
    grey hair ...) is dropped: we can't tell whether it also has dryness etc.
  * Images are de-duplicated across sources (iStock id, then file hash), AND near-duplicate
    photos (perceptual hash) are grouped so a group never spans train and test.
    The CSV gets a `group` column that train.py uses for leak-free cross-validation.
"""

import argparse
import csv
import hashlib
import json
import os
import random
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from grouping import group_ids  # noqa: E402

IMG_EXTS = {".jpg", ".jpeg", ".png"}
SCALP_COLUMNS = ["dryness", "dandruff", "low_density"]


def category_to_column(name):
    n = name.lower()
    if "dandruff" in n:
        return "dandruff"
    if "dry" in n:
        return "dryness"
    if "density" in n or "thinning" in n or ("low" in n and "hair" in n):
        return "low_density"
    return None  # grey hair, alopecia, psoriasis ... not one of our classes


def list_images(folder):
    for dirpath, _, files in os.walk(folder):
        for f in sorted(files):
            if os.path.splitext(f)[1].lower() in IMG_EXTS:
                yield os.path.join(dirpath, f)


def dedupe_key(path):
    m = re.search(r"istockphoto-(\d+)", os.path.basename(path).lower())
    if m:
        return "istock-" + m.group(1)
    with open(path, "rb") as fh:
        return "md5-" + hashlib.md5(fh.read()).hexdigest()


# ------------------------------------------------------------------ balding
def build_balding(raw_root, seed):
    rng = random.Random(seed)
    base = os.path.join(raw_root, "balding", "Dataset")
    rows = []
    for folder, split in [("Train", "train"), ("Validation", "val"), ("Test", "test")]:
        bald = sorted(f for f in os.listdir(os.path.join(base, folder, "Bald")) if os.path.splitext(f)[1].lower() in IMG_EXTS)
        notbald = sorted(f for f in os.listdir(os.path.join(base, folder, "NotBald")) if os.path.splitext(f)[1].lower() in IMG_EXTS)
        n = min(len(bald), len(notbald))  # all Bald, matched by an equal random NotBald sample
        for f in rng.sample(bald, n):
            rows.append([f"balding/Dataset/{folder}/Bald/{f}", 1, split, "kaggle_balding"])
        for f in rng.sample(notbald, n):
            rows.append([f"balding/Dataset/{folder}/NotBald/{f}", 0, split, "kaggle_balding"])
        print(f"  balding {split}: {n} Bald + {n} NotBald (of {len(bald)} / {len(notbald)} available)")
    # Near-duplicate photos must not sit in different splits: a group goes to the
    # "highest priority" split it touches (train > val > test), so test stays clean.
    gids = group_ids([os.path.join(raw_root, r[0]) for r in rows])
    prio = {"train": 0, "val": 1, "test": 2}
    best = {}
    for r, g in zip(rows, gids):
        best[g] = min(best.get(g, 9), prio[r[2]])
    inv = {v: k for k, v in prio.items()}
    moved = 0
    for r, g in zip(rows, gids):
        new = inv[best[g]]
        if new != r[2]:
            r[2] = new
            moved += 1
    print(f"  balding: {moved} images moved so near-duplicates stay in one split")
    for r, g in zip(rows, gids):
        r.append(g)
    return rows


# ------------------------------------------------------------------- scalp
def parse_coco_dataset(dataset_dir, source_name, raw_root):
    """Yield dict(path, labels{col: 0/1/None}, source) for one Roboflow COCO export."""
    out, dropped = [], 0
    # Optional override: a file _column.txt (containing dryness, dandruff or low_density)
    # forces EVERY annotation in this export to that condition. Use it when a set's
    # class is named something unhelpful like "big chunks".
    forced_file = os.path.join(dataset_dir, "_column.txt")
    forced = open(forced_file).read().strip() if os.path.exists(forced_file) else None
    if forced and forced not in SCALP_COLUMNS:
        raise SystemExit(f"{forced_file} must contain one of {SCALP_COLUMNS}, got {forced!r}")
    to_column = (lambda n: forced) if forced else category_to_column
    for split_dir in sorted(os.listdir(dataset_dir)):
        ann = os.path.join(dataset_dir, split_dir, "_annotations.coco.json")
        if not os.path.exists(ann):
            continue
        with open(ann) as fh:
            coco = json.load(fh)
        cats = {c["id"]: c["name"] for c in coco["categories"]}
        assessed = {to_column(n) for n in cats.values()} - {None}
        if not assessed:
            print(f"  WARNING: {source_name}/{split_dir}: no category maps to dryness/dandruff/low_density "
                  f"(categories: {sorted(cats.values())}). Add a _column.txt file to use it.")
        per_image = {img["id"]: set() for img in coco["images"]}
        for a in coco["annotations"]:
            per_image[a["image_id"]].add(cats.get(a["category_id"], "unknown"))
        for img in coco["images"]:
            path = os.path.join(dataset_dir, split_dir, img["file_name"])
            if not os.path.exists(path):
                continue
            names = per_image[img["id"]]
            if forced and not names:  # a single-condition set: an unannotated image is not a confirmed negative
                dropped += 1
                continue
            present = {to_column(n) for n in names} - {None}
            if names and not present:  # only other-condition annotations
                dropped += 1
                continue
            labels = {c: (None if c not in assessed else int(c in present)) for c in SCALP_COLUMNS}
            out.append({"path": path, "labels": labels, "source": source_name})
    print(f"  {source_name}: {len(out)} usable images, {dropped} dropped (unannotated, or only non-target annotations)")
    return out


def build_scalp(raw_root, seed, test_fraction, max_healthy):
    from sklearn.model_selection import train_test_split

    items = []
    main = os.path.join(raw_root, "dryness_dandruff")
    items += parse_coco_dataset(main, "roboflow_hairdata", raw_root)
    extra_root = os.path.join(raw_root, "extra_scalp")
    if os.path.isdir(extra_root):
        for name in sorted(os.listdir(extra_root)):
            if os.path.isdir(os.path.join(extra_root, name)):
                items += parse_coco_dataset(os.path.join(extra_root, name), f"extra_{name}", raw_root)

    healthy_dir = os.path.join(raw_root, "healthy_scalp")
    if os.path.isdir(healthy_dir):
        healthy = list(list_images(healthy_dir))
        random.Random(seed).shuffle(healthy)
        if max_healthy and len(healthy) > max_healthy:
            healthy = healthy[:max_healthy]
        items += [{"path": p, "labels": {c: 0 for c in SCALP_COLUMNS}, "source": "healthy_scalp"} for p in healthy]
        print(f"  healthy_scalp: {len(healthy)} confirmed-healthy images")
    else:
        print("  WARNING: no healthy_scalp folder. The scalp model will have almost no healthy examples "
              "and will over-report conditions. See the README.")

    seen, unique, dup = set(), [], 0
    for it in items:  # earlier sources win
        k = dedupe_key(it["path"])
        if k in seen:
            dup += 1
            continue
        seen.add(k)
        it["key"] = k
        unique.append(it)
    print(f"  removed {dup} duplicate images across sources; {len(unique)} remain")

    # Group near-duplicates (Roboflow exports often contain several near-identical
    # copies of one photo). Whole groups go to train OR test, never both.
    gids = group_ids([it["path"] for it in unique])
    for it, g in zip(unique, gids):
        it["group"] = g

    def combo(it):
        return it["source"] + "|" + "".join("?" if it["labels"][c] is None else str(it["labels"][c]) for c in SCALP_COLUMNS)

    import numpy as np
    from sklearn.model_selection import StratifiedGroupKFold

    combos = [combo(it) for it in unique]
    counts = {c: combos.count(c) for c in set(combos)}
    strat = [c if counts[c] >= 5 else "rare" for c in combos]
    n_splits = max(2, round(1 / test_fraction))
    sgkf = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    _, test_idx = next(sgkf.split(np.zeros(len(unique)), strat, groups=gids))
    test_set = set(test_idx.tolist())

    rows = []
    for i, it in enumerate(unique):
        rel = os.path.relpath(it["path"], raw_root).replace(os.sep, "/")
        vals = ["" if it["labels"][c] is None else it["labels"][c] for c in SCALP_COLUMNS]
        rows.append([rel, *vals, "test" if i in test_set else "train", it["source"], it["group"]])
    return rows


def write_csv(path, header, rows):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def summarize(name, header, rows):
    print(f"\n{name}: {len(rows)} rows")
    si, ti = header.index("split"), header.index("source")
    header = [h for h in header if h != "group"]
    for split in ("train", "val", "test"):
        sub = [r for r in rows if r[si] == split]
        if not sub:
            continue
        parts = []
        for c in header[1:si]:
            ci = header.index(c)
            pos = sum(1 for r in sub if r[ci] == 1)
            neg = sum(1 for r in sub if r[ci] == 0)
            parts.append(f"{c}: {pos}+ / {neg}-")
        print(f"  {split:<5} {len(sub):>5} images | " + " | ".join(parts))
    srcs = {}
    for r in rows:
        srcs[r[ti]] = srcs.get(r[ti], 0) + 1
    print("  sources:", srcs)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--raw-root", required=True)
    p.add_argument("--out-dir", default="data")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--test-fraction", type=float, default=0.2, help="Held-out share of the scalp images")
    p.add_argument("--max-healthy", type=int, default=350, help="Cap on healthy-scalp images (keeps classes balanced)")
    p.add_argument("--skip-balding", action="store_true")
    args = p.parse_args()

    if not args.skip_balding:
        print("Balding (Kaggle):")
        rows = build_balding(args.raw_root, args.seed)
        header = ["filepath", "balding", "split", "source", "group"]
        write_csv(os.path.join(args.out_dir, "balding_labels.csv"), header, rows)
        summarize("balding_labels.csv", header, rows)

    print("\nScalp (Roboflow):")
    rows = build_scalp(args.raw_root, args.seed, args.test_fraction, args.max_healthy)
    header = ["filepath", *SCALP_COLUMNS, "split", "source", "group"]
    write_csv(os.path.join(args.out_dir, "scalp_labels.csv"), header, rows)
    summarize("scalp_labels.csv", header, rows)
    print("\nNext: train each model, then evaluate it on its own test split.")


if __name__ == "__main__":
    main()
