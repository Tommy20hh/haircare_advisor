"""
Smoke test: builds a tiny FAKE dataset (noise images with a colour cue) in the
same folder layout as the real downloads, then runs the whole pipeline:

    build_labels.py -> train.py (balding) -> train.py (scalp, CV) -> evaluate.py x2

It proves the code runs end to end in about a minute, before you spend GPU time.
It does NOT say anything about real accuracy.   python scripts/smoke_test.py
"""

import json
import os
import random
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = sys.executable
rng = np.random.default_rng(0)


def make_img(path, tint):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    arr = np.clip(rng.normal(110, 40, (64, 64, 3)) + np.array(tint), 0, 255).astype(np.uint8)
    Image.fromarray(arr).save(path, "JPEG")


def make_coco(dataset_dir, split, images, categories):
    """images: list of (filename, [category names present])"""
    os.makedirs(os.path.join(dataset_dir, split), exist_ok=True)
    cats = [{"id": i + 1, "name": n} for i, n in enumerate(categories)]
    cid = {n: i + 1 for i, n in enumerate(categories)}
    coco_images, anns = [], []
    for k, (fname, present) in enumerate(images, 1):
        tint = [60 if "dandruff" in present else 0, 60 if "dry hair" in present else 0, 60 if "low hair density" in present else 0]
        make_img(os.path.join(dataset_dir, split, fname), tint)
        coco_images.append({"id": k, "file_name": fname, "width": 64, "height": 64})
        for n in present:
            anns.append({"id": len(anns) + 1, "image_id": k, "category_id": cid[n], "bbox": [0, 0, 10, 10]})
    with open(os.path.join(dataset_dir, split, "_annotations.coco.json"), "w") as fh:
        json.dump({"images": coco_images, "annotations": anns, "categories": cats}, fh)


def build_fake_raw(raw):
    for split, n in [("Train", 12), ("Validation", 6), ("Test", 6)]:
        for cls, tint in [("Bald", [80, 0, 0]), ("NotBald", [0, 0, 80])]:
            for i in range(n * 2):  # more NotBald than needed, like the real set
                if cls == "Bald" and i >= n:
                    break
                make_img(os.path.join(raw, "balding", "Dataset", split, cls, f"{i:04d}.jpg"), tint)

    combos = [["dandruff"], ["dry hair"], ["low hair density"], ["dandruff", "low hair density"], [], ["grey hair"]]
    main_cats = ["dry hair", "dandruff", "low hair density", "grey hair"]
    for split, n in [("train", 30), ("valid", 8), ("test", 8)]:
        imgs = [(f"istockphoto-{split}{i}-612x612_jpg.rf.x{i}.jpg", combos[i % len(combos)]) for i in range(n)]
        make_coco(os.path.join(raw, "dryness_dandruff"), split, imgs, main_cats)
    extra = [(f"extra{i}.jpg", ["dandruff"] if i % 2 else []) for i in range(10)]
    make_coco(os.path.join(raw, "extra_scalp", "dandruff_only"), "train", extra, ["dandruff"])
    for i in range(30):
        make_img(os.path.join(raw, "healthy_scalp", f"healthy{i}.jpg"), [0, 0, 0])


def run(cmd):
    print("\n$", " ".join(os.path.relpath(c) if os.path.exists(c) else c for c in cmd))
    res = subprocess.run(cmd, capture_output=True, text=True)
    print(res.stdout[-1800:])
    if res.returncode != 0:
        print(res.stderr[-3000:])
        raise SystemExit(f"SMOKE TEST FAILED at: {' '.join(cmd[:3])}")


def main():
    with tempfile.TemporaryDirectory() as tmp:
        raw, data, ckpt, res = (os.path.join(tmp, d) for d in ("raw", "data", "ckpt", "results"))
        build_fake_raw(raw)
        run([PY, os.path.join(HERE, "build_labels.py"), "--raw-root", raw, "--out-dir", data, "--max-healthy", "30"])
        common = ["--num-workers", "0", "--no-pretrained", "--batch-size", "8", "--out-dir", ckpt]
        run([PY, os.path.join(ROOT, "src", "train.py"), "--task", "balding", "--labels", os.path.join(data, "balding_labels.csv"),
             "--img-dir", raw, "--epochs", "3", "--warmup-epochs", "1", *common])
        run([PY, os.path.join(ROOT, "src", "train.py"), "--task", "scalp", "--labels", os.path.join(data, "scalp_labels.csv"),
             "--img-dir", raw, "--epochs", "3", "--warmup-epochs", "1", "--folds", "2", *common])
        # new options: strong augmentation, balanced sources, source-blind training
        ckpt2 = os.path.join(tmp, "ckpt_adv")
        run([PY, os.path.join(ROOT, "src", "train.py"), "--task", "scalp", "--labels", os.path.join(data, "scalp_labels.csv"),
             "--img-dir", raw, "--epochs", "3", "--warmup-epochs", "1", "--folds", "2", "--aug", "strong",
             "--balance-sources", "--source-adv", "0.5", "--num-workers", "0", "--no-pretrained", "--batch-size", "8",
             "--out-dir", ckpt2])
        # familiarity gate (downloads the ImageNet MobileNetV2 weights once; needs internet)
        run([PY, os.path.join(HERE, "build_gate.py"), "--task", "scalp", "--labels", os.path.join(data, "scalp_labels.csv"),
             "--img-dir", raw, "--checkpoint", os.path.join(ckpt, "scalp_model.pt"), "--num-workers", "0"])
        for task in ("balding", "scalp"):
            run([PY, os.path.join(ROOT, "src", "evaluate.py"), "--task", task, "--labels", os.path.join(data, f"{task}_labels.csv"),
                 "--img-dir", raw, "--checkpoint", os.path.join(ckpt, f"{task}_model.pt"),
                 "--results-dir", os.path.join(res, task), "--bootstrap", "50", "--num-workers", "0"])
        # Grad-CAM + app helpers on one image
        sys.path.insert(0, os.path.join(ROOT, "src"))
        from gradcam import explain
        from inference import familiarity, image_quality, load_bundle, predict, predict_stable
        from verdict import decide, quality_flags
        bundle = load_bundle(os.path.join(ckpt, "scalp_model.pt"))
        img = Image.open(os.path.join(raw, "healthy_scalp", "healthy0.jpg")).convert("RGB")
        print(predict(bundle, img), image_quality(img))
        fam = familiarity(bundle, img)
        stable = predict_stable(bundle, img)
        assert fam is not None and fam["tier"] in ("familiar", "unfamiliar", "very_unfamiliar")
        for name, info in stable.items():
            print(name, decide(info, fam["tier"], quality_flags(image_quality(img))))
        explain(bundle, img, "dandruff").save(os.path.join(tmp, "cam.png"))
    print("\nSMOKE TEST PASSED - the pipeline runs end to end (numbers on fake data mean nothing).")


if __name__ == "__main__":
    random.seed(0)
    main()
