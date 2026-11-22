"""
Dataset loading for the two classifiers.

Label CSVs look like:
    filepath, <class columns...>, split, source
A class cell may be EMPTY (NaN) when the source dataset never assessed that
condition. Such cells are "unknown", not "absent": they are masked out of the
loss and the metrics instead of being filled with 0.
"""

import io
import os
import random
from typing import List

import numpy as np
import pandas as pd
import torch
from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms

IMAGE_SIZE = 224
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

# Training-time augmentation: simulates different framing, rotation, lighting
# and camera quality so the model doesn't rely on one dataset's photo style.
TRAIN_TRANSFORM = transforms.Compose([
    transforms.RandomResizedCrop(IMAGE_SIZE, scale=(0.6, 1.0), ratio=(0.8, 1.25)),
    transforms.RandomHorizontalFlip(),
    transforms.RandomRotation(20),
    transforms.ColorJitter(brightness=0.35, contrast=0.3, saturation=0.25, hue=0.03),
    transforms.RandomApply([transforms.GaussianBlur(5, sigma=(0.1, 1.5))], p=0.2),
    transforms.ToTensor(),
    transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    transforms.RandomErasing(p=0.15, scale=(0.02, 0.12)),
])

class RandomJPEG:
    """Re-save the photo as a low-quality JPEG (phones/WhatsApp/stock sites compress differently)."""
    def __init__(self, p=0.4, quality=(25, 90)):
        self.p, self.quality = p, quality

    def __call__(self, img):
        if random.random() > self.p:
            return img
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=random.randint(*self.quality))
        buf.seek(0)
        return Image.open(buf).convert("RGB")


class RandomDownUp:
    """Shrink then enlarge: imitates low-resolution / upscaled photos."""
    def __init__(self, p=0.4, scale=(0.3, 0.8)):
        self.p, self.scale = p, scale

    def __call__(self, img):
        if random.random() > self.p:
            return img
        w, h = img.size
        f = random.uniform(*self.scale)
        small = img.resize((max(int(w * f), 16), max(int(h * f), 16)), Image.BILINEAR)
        return small.resize((w, h), Image.BILINEAR)


class RandomNoise:
    """Mild sensor noise on the tensor (after ToTensor, before Normalize)."""
    def __init__(self, p=0.3, std=(0.01, 0.05)):
        self.p, self.std = p, std

    def __call__(self, t):
        if random.random() > self.p:
            return t
        return (t + torch.randn_like(t) * random.uniform(*self.std)).clamp(0, 1)


# "Strong" augmentation = the standard one plus things that differ BETWEEN photo
# sources (colour, compression, resolution, sharpness, noise). Goal: the model can
# no longer tell the source from these cues, so it has to use the scalp/hair itself.
# Every change keeps flakes, scalp visibility and hair density readable.
STRONG_TRAIN_TRANSFORM = transforms.Compose([
    RandomDownUp(p=0.4),
    RandomJPEG(p=0.4),
    transforms.RandomResizedCrop(IMAGE_SIZE, scale=(0.5, 1.0), ratio=(0.75, 1.33)),
    transforms.RandomHorizontalFlip(),
    transforms.RandomRotation(20),
    transforms.ColorJitter(brightness=0.45, contrast=0.4, saturation=0.5, hue=0.06),
    transforms.RandomGrayscale(p=0.25),
    transforms.RandomApply([transforms.GaussianBlur(5, sigma=(0.1, 2.0))], p=0.3),
    transforms.ToTensor(),
    RandomNoise(p=0.3),
    transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    transforms.RandomErasing(p=0.15, scale=(0.02, 0.12)),
])

EVAL_TRANSFORM = transforms.Compose([
    transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
])


def read_labels(csv_path: str, class_names: List[str]) -> pd.DataFrame:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Label file not found: {csv_path}")
    df = pd.read_csv(csv_path)
    missing = [c for c in ["filepath", *class_names] if c not in df.columns]
    if missing:
        raise ValueError(f"{csv_path} is missing columns: {missing}")
    if "split" not in df.columns:
        df["split"] = "train"
    if "source" not in df.columns:
        df["source"] = "unknown"
    df[class_names] = df[class_names].astype(float)  # keeps NaN = unknown
    return df.reset_index(drop=True)


class ConditionDataset(Dataset):
    """Returns (image, labels, mask). mask[i] = 1 if class i was really labelled."""

    def __init__(self, df: pd.DataFrame, img_dir: str, class_names: List[str], transform=None,
                 source_to_idx=None):
        self.df = df.reset_index(drop=True)
        # optional: also return the photo source as an integer (used by source-blind training)
        self.source_to_idx = source_to_idx
        self.img_dir = img_dir
        self.class_names = class_names
        self.transform = transform or EVAL_TRANSFORM
        raw = self.df[class_names].to_numpy(dtype=np.float32)
        self.mask = (~np.isnan(raw)).astype(np.float32)
        self.labels = np.nan_to_num(raw, nan=0.0).astype(np.float32)

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        path = os.path.join(self.img_dir, self.df.loc[idx, "filepath"])
        try:
            image = Image.open(path).convert("RGB")
        except Exception as exc:  # name the file; a bare PIL error doesn't
            raise RuntimeError(f"Could not open image {path}: {exc}") from exc
        out = (
            self.transform(image),
            torch.from_numpy(self.labels[idx]),
            torch.from_numpy(self.mask[idx]),
        )
        if self.source_to_idx is not None:
            out = out + (torch.tensor(self.source_to_idx[self.df.loc[idx, "source"]]),)
        return out
