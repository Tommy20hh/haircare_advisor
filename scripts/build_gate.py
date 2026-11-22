"""
Adds the 'familiarity gate' to a trained checkpoint (see src/gate.py).

    python scripts/build_gate.py --task scalp --labels data/scalp_labels.csv ^
        --img-dir C:\\Haircare\\kaggle_upload\\raw --checkpoint checkpoints/scalp_model.pt

Uses only train/val rows (never test). Writes the gate INTO the checkpoint file
(a backup copy <name>.before_gate.pt is kept the first time).
Optional: --probe-dir FOLDER  prints how unfamiliar your own photos look.
"""
import argparse
import os
import shutil
import sys

import numpy as np
import torch
from PIL import Image
from torch.utils.data import DataLoader

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from dataset import ConditionDataset, EVAL_TRANSFORM, read_labels  # noqa: E402
from gate import build_gate, embed_batch, embed_image, gate_check  # noqa: E402
from model import TASKS  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--task", required=True, choices=list(TASKS))
    p.add_argument("--labels", required=True)
    p.add_argument("--img-dir", required=True)
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--probe-dir", default=None)
    p.add_argument("--num-workers", type=int, default=2)
    args = p.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ckpt = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    df = read_labels(args.labels, TASKS[args.task])
    df = df[df["split"].isin(["train", "val"])].reset_index(drop=True)
    groups = df["group"].to_numpy() if "group" in df.columns else np.arange(len(df))
    ds = ConditionDataset(df, args.img_dir, TASKS[args.task], EVAL_TRANSFORM)
    loader = DataLoader(ds, batch_size=64, shuffle=False, num_workers=args.num_workers)
    bank = np.concatenate([embed_batch(x, device) for x, _, _ in loader])
    gate = build_gate(bank, groups)
    from gate import _extractor
    gate["extractor"] = {k: v.cpu() for k, v in _extractor(device).state_dict().items()}  # so the app needs no internet
    print(f"Gate built from {len(bank)} training photos.")
    print("Typical distance to the nearest training photos:", gate["train_distance_percentiles"])
    print(f"familiar up to {gate['familiar_max']:.3f}; very unfamiliar above {gate['unfamiliar_max']:.3f}")

    backup = args.checkpoint.replace(".pt", ".before_gate.pt")
    if not os.path.exists(backup):
        shutil.copy2(args.checkpoint, backup)
    ckpt["gate"] = gate
    torch.save(ckpt, args.checkpoint)
    print("Saved gate into", args.checkpoint)

    if args.probe_dir:
        print("\nYour probe photos:")
        for f in sorted(os.listdir(args.probe_dir)):
            if os.path.splitext(f)[1].lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                r = gate_check(gate, embed_image(Image.open(os.path.join(args.probe_dir, f)), device, gate['extractor']))
                print(f"  {f:<40} distance {r['distance']:.3f} -> {r['tier']}")


if __name__ == "__main__":
    main()
