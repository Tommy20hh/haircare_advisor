"""Stand-in for service.engine.Engine so the API can be tested without torch or checkpoints.
It uses the REAL verdict rules; only the model scores are invented from simple image statistics.
Used by tests only, never offered to users."""

import numpy as np
from PIL import Image

from settings import SLOTS
from verdict import decide, mismatch_verdict, photo_status, quality_flags


class FakeEngine:
    def __init__(self, missing=()):
        self.missing = set(missing)

    def models(self):
        return [{"slot": s, "task": sp["task"], "loaded": s not in self.missing, "model_version": "fake-1",
                 "classes": sp["conditions"]} for s, sp in SLOTS.items()]

    def has(self, slot):
        return slot not in self.missing

    def assess(self, slot, image: Image.Image):
        arr = np.asarray(image.convert("RGB"), dtype=np.float32)
        r, g, b = arr[..., 0].mean(), arr[..., 1].mean(), arr[..., 2].mean()
        tier = "very_unfamiliar" if b > r + 40 else ("unfamiliar" if arr.mean() < 90 else "familiar")
        flags = quality_flags({"width": image.size[0], "height": image.size[1], "brightness": float(arr.mean()),
                               "sharpness": 300.0 if arr.std() > 5 else 1.0})
        status = photo_status(tier, flags)
        fam = {"distance": 0.2, "tier": tier, "familiar_max": 0.3, "unfamiliar_max": 0.5}
        names = SLOTS[slot]["conditions"]
        if status == "mismatch":
            return {"status": status, "tier": tier, "fam": fam, "flags": flags, "results": None,
                    "verdicts": {n: mismatch_verdict(flags) for n in names}}
        results = {n: {"prob": float(min(0.95, r / 255)), "threshold": 0.5, "status": bool(r / 255 >= 0.5),
                       "spread": 0.05, "views_positive": 4, "n_views": 4} for n in names}
        return {"status": status, "tier": tier, "fam": fam, "flags": flags, "results": results,
                "verdicts": {n: decide(i, tier, flags) for n, i in results.items()}}

    def heatmap(self, slot, image, condition):
        return "data:image/png;base64,iVBORw0KGgo="
