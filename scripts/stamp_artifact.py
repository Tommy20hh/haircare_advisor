"""
Writes the artifact metadata into a checkpoint WITHOUT retraining (lecture: artifact + versioning,
feature schema, train/serve skew). Adds: model_version, preprocessing, feature_schema.
A backup <name>.before_stamp.pt is kept.

    python scripts/stamp_artifact.py checkpoints/balding_model.pt checkpoints/scalp_model.pt
"""
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

import torch  # noqa: E402

from settings import MODEL_VERSION  # noqa: E402


def main(paths):
    for path in paths:
        ckpt = torch.load(path, map_location="cpu", weights_only=False)
        backup = path[:-3] + ".before_stamp.pt"
        if not os.path.exists(backup):
            shutil.copy2(path, backup)
        ckpt["model_version"] = f"{ckpt.get('task', 'model')}-{MODEL_VERSION}"
        ckpt["preprocessing"] = {"resize": "see src/dataset.py EVAL_TRANSFORM", "normalize": "ImageNet mean/std", "colour": "RGB"}
        ckpt["feature_schema"] = {"input": "one RGB photo (JPEG/PNG/WebP, <=10 MB)", "classes": ckpt["class_names"],
                                  "output": "calibrated probability per class + threshold + True/False/None"}
        ckpt["stamped_at"] = time.strftime("%Y-%m-%d")
        torch.save(ckpt, path)
        print("stamped", path, "->", ckpt["model_version"])


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    main(sys.argv[1:])
