"""Loads the trained models once and runs one photo through the pipeline (lecture: model artifact,
versioning, load at start-up, cold start). The API talks to this small interface only, so tests can
plug in a fake engine without torch."""

import base64
import hashlib
import os
import threading
from io import BytesIO
from typing import Dict, List, Optional

from PIL import Image

from pipeline import assess
from settings import SLOTS


class Engine:
    def __init__(self, checkpoint_dir: str):
        from inference import load_bundle  # imported here: torch is only needed for the real engine
        self.bundles: Dict[str, object] = {}
        self.versions: Dict[str, str] = {}
        # Grad-CAM attaches a hook to the shared model, so two requests inside the models at once could corrupt each
        # other. One photo check takes about a second and this app serves one person at a time, so we simply take turns.
        self._lock = threading.Lock()
        for slot, spec in SLOTS.items():
            path = os.path.join(checkpoint_dir, f"{spec['task']}_model.pt")
            bundle = load_bundle(path)
            if bundle is None:
                continue
            self.bundles[slot] = bundle
            self.versions[slot] = (bundle.meta or {}).get("model_version") or self._fingerprint(path)

    @staticmethod
    def _fingerprint(path: str) -> str:
        h = hashlib.sha1()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return "sha1-" + h.hexdigest()[:8]

    def warm_up(self) -> None:
        """One dummy pass so the first real visitor does not pay the cold-start cost."""
        for slot, bundle in self.bundles.items():
            try:
                assess(bundle, Image.new("RGB", (256, 256), (128, 110, 100)))
            except Exception:
                pass

    def models(self) -> List[dict]:
        out = []
        for slot, spec in SLOTS.items():
            b = self.bundles.get(slot)
            out.append({"slot": slot, "task": spec["task"], "loaded": b is not None,
                        "model_version": self.versions.get(slot), "classes": list(b.class_names) if b else spec["conditions"]})
        return out

    def has(self, slot: str) -> bool:
        return slot in self.bundles

    def assess(self, slot: str, image: Image.Image) -> dict:
        with self._lock:
            return assess(self.bundles[slot], image)

    def heatmap(self, slot: str, image: Image.Image, condition: str) -> Optional[str]:
        from gradcam import explain
        with self._lock:
            overlay = explain(self.bundles[slot], image, condition)
        buf = BytesIO()
        overlay.convert("RGB").save(buf, "PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
