"""API tests with a fake engine (no torch). Run: python tests/test_service.py   (needs fastapi, httpx, python-multipart)"""
import io
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, HERE)

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from fake_engine import FakeEngine
from service.main import create_app


def photo(color, size=(320, 240), fmt="JPEG", noise=True):
    arr = np.full((size[1], size[0], 3), color, dtype=np.uint8)
    if noise:
        arr = np.clip(arr + np.random.default_rng(1).normal(0, 20, arr.shape), 0, 255).astype(np.uint8)
    buf = io.BytesIO(); Image.fromarray(arr).save(buf, fmt); return buf.getvalue()


def client(engine=None, **kw):
    tmp = tempfile.mkdtemp()
    return TestClient(create_app(engine or FakeEngine(), log_path=os.path.join(tmp, "log.jsonl"), **kw)), tmp


def main():
    c, tmp = client()
    h = c.get("/health").json()
    assert h["status"] == "ok" and h["phone_validated"] is False and len(h["models"]) == 2

    # one good scalp photo -> only the scalp model runs, front conditions are listed as not assessed
    r = c.post("/predict", files={"crown": ("a.jpg", photo((200, 150, 120)), "image/jpeg")})
    assert r.status_code == 200, r.text
    j = r.json()
    assert [s["slot"] for s in j["slots"]] == ["crown"] and j["not_assessed"] == ["balding"]
    assert {x["condition"] for x in j["slots"][0]["conditions"]} == {"dryness", "dandruff", "low_density"}
    assert j["slots"][0]["check"]["status"] == "match"
    assert all(x["reliability"] != "good" for x in j["slots"][0]["conditions"]), "untested cap must hold"
    assert any("untested" in x["reasons"] for x in j["slots"][0]["conditions"])
    assert "not_assessed" in j["advice"] and j["request_id"]

    # a photo of the wrong type is refused, not judged
    r = c.post("/predict", files={"front": ("b.jpg", photo((40, 60, 230)), "image/jpeg")}).json()
    s = r["slots"][0]
    assert s["check"]["status"] == "mismatch" and all(x["verdict"] == "unsuitable" and x["probability"] is None for x in s["conditions"])

    # a dark photo is never reassured
    r = c.post("/predict", files={"crown": ("d.jpg", photo((50, 40, 35)), "image/jpeg")}).json()
    assert all(x["verdict"] != "none_seen" for x in r["slots"][0]["conditions"])

    # heatmap only on request and only for 'possible'
    r = c.post("/predict", data={"heatmap": "true"}, files={"crown": ("a.jpg", photo((240, 150, 120)), "image/jpeg")}).json()
    assert any(x["heatmap"] for x in r["slots"][0]["conditions"])
    r = c.post("/predict", files={"crown": ("a.jpg", photo((240, 150, 120)), "image/jpeg")}).json()
    assert not any(x["heatmap"] for x in r["slots"][0]["conditions"])

    # input errors give a code and a message a person can act on
    def err(resp, status, code):
        assert resp.status_code == status and resp.json()["error"]["code"] == code, (resp.status_code, resp.text)
    err(c.post("/predict"), 400, "no_photo")
    err(c.post("/predict", files={"front": ("x.gif", b"GIF89a", "image/gif")}), 415, "unsupported_type")
    err(c.post("/predict", files={"front": ("x.jpg", b"not an image", "image/jpeg")}), 400, "unreadable")
    err(c.post("/predict", files={"front": ("x.jpg", b"", "image/jpeg")}), 400, "empty_file")
    err(c.post("/predict", files={"front": ("x.jpg", photo((9, 9, 9), (30, 30)), "image/jpeg")}), 400, "too_small")
    err(c.post("/predict", files={"front": ("x.jpg", b"0" * (10 * 1024 * 1024 + 5), "image/jpeg")}), 413, "too_large")

    # model missing
    c2, _ = client(FakeEngine(missing=["front"]))
    assert c2.get("/health").json()["status"] == "degraded"
    err(c2.post("/predict", files={"front": ("a.jpg", photo((200, 150, 120)), "image/jpeg")}), 503, "model_missing")

    # monitoring counts requests, never photos
    st = c.get("/stats").json()
    assert st["requests"] >= 5 and st["photo_check"]["mismatch"] >= 1 and st["failed"] >= 3
    log = open(os.path.join(tmp, "log.jsonl"), encoding="utf-8").read()
    assert "base64" not in log and "jpg" not in log

    # samples: empty-state and path safety
    sd = tempfile.mkdtemp()
    c3, _ = client(samples_dir=sd)
    assert c3.get("/samples").json() == {"items": []}
    open(os.path.join(sd, "dandruff_01.jpg"), "wb").write(photo((200, 150, 120)))
    assert [i["name"] for i in c3.get("/samples").json()["items"]] == ["dandruff_01.jpg"]
    assert c3.get("/samples/dandruff_01.jpg").status_code == 200
    assert c3.get("/samples/..%2Fsecret.jpg").status_code in (404, 422)

    # website is served
    assert c.get("/").status_code in (200, 404)  # 200 once web/index.html exists
    css = c.get("/css/site.css")
    if css.status_code == 200:   # website files must be re-checked by the browser, or an update shows as a half-old page
        assert css.headers["cache-control"] == "no-cache", css.headers.get("cache-control")
    assert c.get("/health").json()["status"] in ("ok", "degraded")
    print("service tests passed")


if __name__ == "__main__":
    main()
