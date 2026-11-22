"""Request log + live statistics (lecture: monitoring, drift, silent decay). Photos are NEVER stored:
a line holds only counts, verdict keys, timings and the photo-type check result."""

import json
import os
import threading
import time
from collections import Counter
from typing import Dict, List, Optional


class Monitor:
    def __init__(self, path: Optional[str] = None, keep: int = 2000, max_bytes: int = 2 * 1024 * 1024):
        self.path = path
        self.keep = keep
        self.max_bytes = max_bytes      # when the file grows past this it is rewritten with only the newest rows
        self.rows: List[dict] = []
        self.lock = threading.Lock()
        if path and os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as fh:
                    self.rows = [json.loads(x) for x in fh if x.strip()][-keep:]
            except Exception:
                self.rows = []

    def record(self, row: dict) -> None:
        row = dict(row, ts=round(time.time(), 1))
        with self.lock:
            self.rows.append(row)
            self.rows = self.rows[-self.keep:]
            if self.path:
                try:
                    os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
                    with open(self.path, "a", encoding="utf-8") as fh:
                        fh.write(json.dumps(row) + "\n")
                    if os.path.getsize(self.path) > self.max_bytes:
                        self._compact()
                except OSError:
                    pass  # logging must never break a prediction

    def _compact(self) -> None:
        """Keep only the newest rows (called with the lock held). Written to a temp file first, so a crash cannot truncate the log."""
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.writelines(json.dumps(r) + "\n" for r in self.rows)
        os.replace(tmp, self.path)

    def stats(self) -> Dict:
        with self.lock:
            rows = list(self.rows)
        ok = [r for r in rows if r.get("ok")]
        slots = [s for r in ok for s in r.get("slots", [])]
        checks = Counter(s["check"] for s in slots)
        verdicts = Counter(v for s in slots for v in s.get("verdicts", []))
        lat = sorted(r["latency_ms"] for r in ok if "latency_ms" in r)

        def pct(p):
            return lat[min(len(lat) - 1, int(p * len(lat)))] if lat else None

        n_slots = len(slots)
        return {
            "requests": len(rows), "failed": len(rows) - len(ok), "photos_checked": n_slots,
            "photo_check": {k: checks.get(k, 0) for k in ("match", "partial", "mismatch")},
            "share_outside_trained_type": round((checks.get("partial", 0) + checks.get("mismatch", 0)) / n_slots, 3) if n_slots else None,
            "verdicts": {k: verdicts.get(k, 0) for k in ("possible", "none_seen", "unsure", "unsuitable")},
            "latency_ms": {"median": pct(0.5), "p95": pct(0.95)},
        }
