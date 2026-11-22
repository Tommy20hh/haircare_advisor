"""
Near-duplicate grouping, so copies of the same photo never end up on both sides
of a train/test split (that would make test scores look better than they are).

A 'difference hash' (dHash) is a 256-bit fingerprint of a small grey thumbnail.
Two photos whose fingerprints differ by <= max_bits bits are treated as the same
photo (resized, re-saved, mirrored-by-export, lightly edited...). Duplicates are
joined into groups; a group must stay inside ONE split.

Only numpy and Pillow are needed (no torch).
"""

from typing import List, Sequence

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None  # some stock photos are huge; we only make a thumbnail


def dhash(path: str, size: int = 16) -> np.ndarray:
    with Image.open(path) as im:
        im.draft("L", (size * 8, size * 8))  # fast JPEG decode at reduced size
        im = im.convert("L").resize((size + 1, size), Image.LANCZOS)
    a = np.asarray(im, dtype=np.int16)
    return (a[:, 1:] > a[:, :-1]).flatten().astype(np.uint8)


def group_ids(paths: Sequence[str], max_bits: int = 10) -> List[int]:
    """Return one integer group id per path. Unreadable images get their own group."""
    hashes, ok = [], []
    for i, p in enumerate(paths):
        try:
            hashes.append(dhash(p))
            ok.append(i)
        except Exception:
            hashes.append(None)
    parent = list(range(len(paths)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    if ok:
        H = np.stack([hashes[i] for i in ok]).astype(np.int16)
        for a in range(len(ok) - 1):
            d = (H[a + 1:] != H[a]).sum(axis=1)
            for off in np.nonzero(d <= max_bits)[0]:
                parent[find(ok[a])] = find(ok[a + 1 + off])
    return [find(i) for i in range(len(paths))]
