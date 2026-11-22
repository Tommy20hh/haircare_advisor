"""
Checks demo photos against the TRAINING images so the demo is not a re-run of training data
(leakage, in the professor's words). Uses a difference hash; small distance = near-duplicate.

    python scripts/check_demo_photos.py --demo demo_samples --train-dir <folder with training images> [--max-dist 6]

Reports each demo photo's closest training image. Replace any photo flagged NEAR-DUPLICATE.
"""
import argparse
import os

import numpy as np
from PIL import Image, ImageOps

EXT = (".jpg", ".jpeg", ".png", ".webp")


def dhash(path, size=16):
    im = ImageOps.exif_transpose(Image.open(path)).convert("L").resize((size + 1, size))
    a = np.asarray(im, dtype=np.int16)
    return (a[:, 1:] > a[:, :-1]).flatten()


def images(root):
    for d, _, fs in os.walk(root):
        for f in fs:
            if f.lower().endswith(EXT):
                yield os.path.join(d, f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", default="demo_samples")
    ap.add_argument("--train-dir", required=True)
    ap.add_argument("--max-dist", type=int, default=6, help="out of 256 bits")
    a = ap.parse_args()
    train = []
    for p in images(a.train_dir):
        try:
            train.append((p, dhash(p)))
        except Exception:
            pass
    print(f"{len(train)} training images hashed")
    bad = 0
    for p in sorted(images(a.demo)):
        h = dhash(p)
        best = min(((int((h != th).sum()), tp) for tp, th in train), default=(999, ""))
        near = best[0] <= a.max_dist
        bad += near
        print(f"{os.path.basename(p):28s} closest distance {best[0]:3d}  " + ("NEAR-DUPLICATE  <- replace this photo" if near else "ok"))
    print("\nAll demo photos are new to the model." if not bad else f"\n{bad} photo(s) need replacing.")


if __name__ == "__main__":
    main()
