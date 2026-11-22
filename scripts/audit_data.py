"""
Data audit: finds duplicate / near-duplicate images that sit in DIFFERENT splits
(= test leakage), and reports label counts per source.

    python scripts/audit_data.py --raw-root C:\\Haircare\\kaggle_upload\\raw \
        --labels data/scalp_labels.csv --out docs/audit_scalp.json

Uses only numpy / Pillow / pandas (no torch). A 'perceptual hash' is a tiny
fingerprint of what an image looks like; near-identical photos (resized, re-saved
or lightly edited) get fingerprints that differ by only a few bits.
"""
import argparse
import json
import os
from collections import Counter, defaultdict

import numpy as np
import pandas as pd
from PIL import Image


def dhash(path, size=16):
    """Difference hash: compares neighbouring pixels of a small grey thumbnail."""
    with Image.open(path) as im:
        im = im.convert("L").resize((size + 1, size), Image.LANCZOS)
    a = np.asarray(im, dtype=np.int16)
    return (a[:, 1:] > a[:, :-1]).flatten()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--raw-root", required=True)
    p.add_argument("--labels", required=True)
    p.add_argument("--out", default="docs/audit.json")
    p.add_argument("--max-bits", type=int, default=10, help="Hamming distance (of 256 bits) counted as near-duplicate")
    args = p.parse_args()

    df = pd.read_csv(args.labels)
    hashes, bad = [], []
    for fp in df["filepath"]:
        try:
            hashes.append(dhash(os.path.join(args.raw_root, fp)))
        except Exception as e:  # unreadable image
            hashes.append(None)
            bad.append(fp)
    ok = [i for i, h in enumerate(hashes) if h is not None]
    H = np.stack([hashes[i] for i in ok]).astype(np.uint8)

    # pairwise Hamming distance (n is small enough for a full matrix)
    packed = H.astype(np.int16)
    pairs = []
    for a in range(len(ok)):
        d = (packed[a + 1:] != packed[a]).sum(axis=1)
        for off in np.nonzero(d <= args.max_bits)[0]:
            b = a + 1 + off
            pairs.append((ok[a], ok[b], int(d[off])))

    cross = [(i, j, d) for i, j, d in pairs if df.loc[i, "split"] != df.loc[j, "split"]]
    same_split = len(pairs) - len(cross)

    # connected groups of near-duplicates -> usable as 'group id' for leak-free splitting
    parent = list(range(len(df)))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for i, j, _ in pairs:
        parent[find(i)] = find(j)
    groups = defaultdict(list)
    for i in range(len(df)):
        groups[find(i)].append(i)
    multi = {g: m for g, m in groups.items() if len(m) > 1}

    by_source = {}
    label_cols = [c for c in df.columns if c not in ("filepath", "split", "source")]
    for src, sub in df.groupby("source"):
        entry = {"n": int(len(sub)), "split": sub["split"].value_counts().to_dict()}
        for c in label_cols:
            entry[c] = {"pos": int((sub[c] == 1).sum()), "neg": int((sub[c] == 0).sum()),
                        "unknown": int(sub[c].isna().sum())}
        by_source[src] = entry

    leaks_by_source = Counter()
    for i, j, _ in cross:
        leaks_by_source[f"{df.loc[i,'source']} <-> {df.loc[j,'source']}"] += 1

    # images in the test split that have a near-duplicate in train/val
    test_leaked = sorted({i if df.loc[i, "split"] == "test" else j for i, j, _ in cross
                          if "test" in (df.loc[i, "split"], df.loc[j, "split"])})
    n_test = int((df["split"] == "test").sum())

    report = {
        "n_images": int(len(df)), "unreadable": bad,
        "near_duplicate_pairs_total": len(pairs),
        "near_duplicate_pairs_same_split": same_split,
        "near_duplicate_pairs_across_splits": len(cross),
        "duplicate_groups": len(multi),
        "largest_group": max((len(m) for m in multi.values()), default=1),
        "test_images_with_a_near_duplicate_in_train_or_val": len(test_leaked),
        "n_test": n_test,
        "leak_pairs_by_source": dict(leaks_by_source),
        "by_source": by_source,
        "hamming_threshold_bits_of_256": args.max_bits,
    }
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(report, fh, indent=2)
    # also save group ids so splits can be rebuilt leak-free
    out_groups = os.path.splitext(args.out)[0] + "_groups.csv"
    gid = {i: g for g, m in groups.items() for i in m}
    pd.DataFrame({"filepath": df["filepath"], "group_id": [gid[i] for i in range(len(df))]}).to_csv(out_groups, index=False)
    print(json.dumps({k: v for k, v in report.items() if k != "by_source"}, indent=2))
    print(json.dumps(by_source, indent=2))


if __name__ == "__main__":
    main()
