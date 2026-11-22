"""
Shows how the app would treat YOUR photos, without opening the app.

    python scripts/probe_photos.py --task scalp --folder C:\\Haircare\\my_photos
    python scripts/probe_photos.py --task balding --folder C:\\Haircare\\my_front_photos

Per photo: familiarity tier (is it like the training photos?), quality flags, and each
condition's verdict. Photos stay on your computer; nothing is saved.
"""
import argparse
import os
import sys

from PIL import Image, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
from inference import familiarity, image_quality, load_bundle, predict_stable  # noqa: E402
from verdict import decide, quality_flags  # noqa: E402

a = argparse.ArgumentParser()
a.add_argument("--task", required=True, choices=["balding", "scalp"])
a.add_argument("--folder", required=True)
a.add_argument("--checkpoint", default=os.path.join(HERE, "..", "checkpoints"))
args = a.parse_args()

bundle = load_bundle(os.path.join(args.checkpoint, f"{args.task}_model.pt"))
if bundle is None:
    raise SystemExit("Checkpoint not found.")
if not bundle.gate:
    print("WARNING: this checkpoint has no familiarity gate (run build_gate.py). Negatives will show as 'unsure'.")
if bundle.gate:
    g = bundle.gate
    print("Training photos' own distances (typical = what 'familiar' means):", {k: round(v, 3) for k, v in g["train_distance_percentiles"].items()})
    print(f"Tier limits: familiar <= {g['familiar_max']:.3f}, very unfamiliar > {g['unfamiliar_max']:.3f}")
for f in sorted(os.listdir(args.folder)):
    if os.path.splitext(f)[1].lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
        continue
    img = ImageOps.exif_transpose(Image.open(os.path.join(args.folder, f))).convert("RGB")
    img.thumbnail((1024, 1024))
    fam = familiarity(bundle, img)
    flags = quality_flags(image_quality(img))
    tier = fam["tier"] if fam else None
    results = predict_stable(bundle, img)
    print(f"\n{f}: familiarity = {fam['tier'] if fam else 'n/a'}"
          f"{' (distance %.3f)' % fam['distance'] if fam else ''}; quality flags = {flags or 'none'}")
    for name, info in results.items():
        v = decide(info, tier, flags)
        print(f"   {name:<12} score {info['prob']:.2f} (line {info['threshold']:.2f}) -> {v['verdict']:<10} reliability {v['reliability']:<8} {v['reasons']}")
