"""Privacy and security tests for the service (no torch needed).
Run: python tests/test_security.py     (needs fastapi, httpx, python-multipart, pillow, numpy)

Each block below proves one promise the app makes about personal photos:
  1. photos stay in memory, are not logged and are not kept;
  2. a file is judged by what it REALLY is, not by what the browser claims;
  3. oversized uploads and decompression bombs are refused before they are decoded;
  4. every response carries browser protections, and no response allows other websites to call the API;
  5. a crash never shows a stack trace or a server path;
  6. two requests never run inside the models at the same time;
  7. the request log cannot grow forever.
"""
import io
import json
import os
import sys
import tempfile
import threading
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, HERE)

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from fake_engine import FakeEngine
from service.main import create_app
from service.monitor import Monitor


def photo(color=(200, 150, 120), size=(320, 240), fmt="JPEG", noise=True, quality=90):
    arr = np.full((size[1], size[0], 3), color, dtype=np.uint8)
    if noise:
        arr = np.clip(arr + np.random.default_rng(1).normal(0, 20, arr.shape), 0, 255).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, fmt, **({"quality": quality} if fmt == "JPEG" else {}))
    return buf.getvalue()


def client(engine=None, **kw):
    tmp = tempfile.mkdtemp()
    return TestClient(create_app(engine or FakeEngine(), log_path=os.path.join(tmp, "log.jsonl"), **kw)), tmp


def err(resp, status, code):
    assert resp.status_code == status and resp.json()["error"]["code"] == code, (resp.status_code, resp.text[:200])
    return resp


def test_browser_protections():
    c, _ = client()
    for path in ("/health", "/stats", "/"):
        r = c.get(path)
        assert r.headers["x-content-type-options"] == "nosniff", path
        assert r.headers["referrer-policy"] == "no-referrer" and r.headers["x-frame-options"] == "DENY", path
        csp = r.headers["content-security-policy"]
        assert "default-src 'self'" in csp and "unsafe-inline" not in csp and "unsafe-eval" not in csp, csp
        assert "frame-ancestors 'none'" in csp and "object-src 'none'" in csp
    for path in ("/health", "/stats"):
        assert c.get(path).headers["cache-control"] == "no-store"
    r = c.post("/predict", files={"crown": ("a.jpg", photo(), "image/jpeg")})
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"   # answers and heat maps are never cached
    # the interactive docs load their viewer from a CDN, so only they are exempt from the strict policy
    d = c.get("/docs")
    assert d.status_code == 200 and "content-security-policy" not in d.headers and d.headers["x-content-type-options"] == "nosniff"
    # no CORS: another website cannot call the API from a visitor's browser
    r = c.options("/predict", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in r.headers
    assert "access-control-allow-origin" not in c.get("/health", headers={"Origin": "http://evil.example"}).headers


def test_docs_can_be_switched_off():
    os.environ["HAIR_DISABLE_DOCS"] = "1"
    try:
        c, _ = client()
        assert c.get("/docs").status_code == 404 and c.get("/openapi.json").status_code == 404
        assert c.get("/health").status_code == 200
    finally:
        del os.environ["HAIR_DISABLE_DOCS"]
    c, _ = client()
    assert c.get("/docs").status_code == 200


def test_real_file_type_counts():
    c, _ = client()
    gif = io.BytesIO(); Image.new("RGB", (100, 100), (9, 9, 9)).save(gif, "GIF")
    bmp = io.BytesIO(); Image.new("RGB", (100, 100), (9, 9, 9)).save(bmp, "BMP")
    # a GIF / BMP that claims to be a JPEG or PNG is refused as unsupported
    err(c.post("/predict", files={"front": ("a.jpg", gif.getvalue(), "image/jpeg")}), 415, "unsupported_type")
    err(c.post("/predict", files={"front": ("a.png", bmp.getvalue(), "image/png")}), 415, "unsupported_type")
    # a text file that claims to be an image is unreadable
    err(c.post("/predict", files={"front": ("a.jpg", b"<script>alert(1)</script>", "image/jpeg")}), 400, "unreadable")
    # a real PNG sent with the wrong label is still a fine photo
    assert c.post("/predict", files={"crown": ("a.jpg", photo(fmt="PNG"), "image/jpeg")}).status_code == 200
    # the browser label is only a quick first filter
    err(c.post("/predict", files={"front": ("a.pdf", photo(), "application/pdf")}), 415, "unsupported_type")


def test_oversized_uploads_are_refused_early():
    c, _ = client()
    # declared size far above the limit: refused before the body is read, and the refusal itself is protected
    r = c.post("/predict", content=b"x", headers={"Content-Length": str(30 * 1024 * 1024), "Content-Type": "multipart/form-data; boundary=x"})
    err(r, 413, "too_large")
    assert r.headers["x-content-type-options"] == "nosniff" and r.json()["error"]["request_id"]   # a refusal can be traced like any answer
    # an upload that does not declare its size is refused (a stream of unknown length could be endless)
    r = c.post("/predict", content=iter([b"--x\r\n", b"--x--\r\n"]), headers={"Content-Type": "multipart/form-data; boundary=x"})
    err(r, 411, "length_required")
    # a tiny file with an enormous picture inside (a "decompression bomb") is refused from its header, undecoded
    buf = io.BytesIO(); Image.new("1", (9000, 9000)).save(buf, "PNG")
    assert len(buf.getvalue()) < 1024 * 1024, "the bomb must be small, otherwise this test proves nothing"
    err(c.post("/predict", files={"front": ("b.png", buf.getvalue(), "image/png")}), 413, "too_many_pixels")
    # a photo just under every limit still works
    assert c.post("/predict", files={"crown": ("a.jpg", photo(size=(2000, 1500)), "image/jpeg")}).status_code == 200


def test_photos_stay_in_memory_and_out_of_the_log():
    import starlette.datastructures as ds
    seen = []
    original = ds.UploadFile.__init__

    def spy(self, *a, **k):
        original(self, *a, **k); seen.append(self)
    ds.UploadFile.__init__ = spy
    try:
        c, tmp = client()
        big = photo(size=(1600, 1600), quality=95)                      # a phone-sized photo, above Starlette's 1 MB spill point
        assert len(big) > 1024 * 1024 + 1, len(big)
        r = c.post("/predict", files={"front": ("my_secret_name.jpg", big, "image/jpeg")})
        assert r.status_code == 200, r.text
    finally:
        ds.UploadFile.__init__ = original
    assert seen and not any(getattr(u.file, "_rolled", False) for u in seen), "an upload was spilled to a temporary file on disk"
    # the log holds counts and verdict keys only: no file name, no pixels, nothing that identifies the photo
    log = open(os.path.join(tmp, "log.jsonl"), encoding="utf-8").read()
    assert "my_secret_name" not in log and "base64" not in log and ".jpg" not in log
    assert os.listdir(tmp) == ["log.jsonl"], os.listdir(tmp)           # no photo was left in the service's folder
    row = json.loads(log.strip().splitlines()[-1])
    assert row["model_versions"] == {"front": "fake-1"} and row["app_version"], row
    assert set(row["slots"][0]["confidence"]) == {"balding"}, row
    stats = json.dumps(c.get("/stats").json())
    assert "my_secret_name" not in stats


class Crashing(FakeEngine):
    def assess(self, slot, image):
        raise RuntimeError("secret-boom at C:\\Haircare\\service\\engine.py line 42")


def test_a_crash_shows_nothing_internal():
    import logging
    logging.getLogger("hair_advisor").disabled = True                     # the crash details go to the server console; keep the test output clean
    c, tmp = client(Crashing())
    r = c.post("/predict", files={"front": ("a.jpg", photo(), "image/jpeg")})
    assert r.status_code == 500 and r.json()["error"]["code"] == "server_error" and r.json()["error"]["request_id"]
    for leak in ("secret-boom", "Traceback", "engine.py", "C:\\", "line 42"):
        assert leak not in r.text, leak
    assert r.headers["x-content-type-options"] == "nosniff" and "content-security-policy" in r.headers   # even a crash is protected
    assert c.get("/health").status_code == 200                          # the service survives and keeps answering
    st = c.get("/stats").json()
    assert st["failed"] >= 1
    # input errors never leak either
    for resp in (c.post("/predict"), c.post("/predict", files={"front": ("x.jpg", b"nope", "image/jpeg")})):
        assert "Traceback" not in resp.text and "site-packages" not in resp.text
    logging.getLogger("hair_advisor").disabled = False


def test_no_path_traversal():
    sd = tempfile.mkdtemp()
    c, _ = client(samples_dir=sd)
    for url in ("/samples/..%2F..%2Fsecret.jpg", "/samples/%2e%2e%2fsettings.jpg", "/..%2f..%2fREADME.md", "/%2e%2e/src/settings.py", "/../src/settings.py"):
        assert c.get(url).status_code in (404, 422, 400), url
    assert "MODEL_VERSION" not in c.get("/..%2fsrc%2fsettings.py").text


def test_models_run_one_request_at_a_time():
    # service.engine imports torch through the pipeline; a stand-in module lets this test run anywhere
    stub = types.ModuleType("pipeline")
    state = {"now": 0, "max": 0}
    guard = threading.Lock()

    def slow_assess(bundle, image):
        with guard:
            state["now"] += 1; state["max"] = max(state["max"], state["now"])
        time.sleep(0.03)
        with guard:
            state["now"] -= 1
        return {"ok": True}
    stub.assess = slow_assess
    saved = sys.modules.get("pipeline")
    sys.modules["pipeline"] = stub
    sys.modules.pop("service.engine", None)
    try:
        from service.engine import Engine
        e = object.__new__(Engine)
        e.bundles, e.versions, e._lock = {"front": object()}, {}, threading.Lock()
        threads = [threading.Thread(target=lambda: e.assess("front", None)) for _ in range(8)]
        [t.start() for t in threads]; [t.join() for t in threads]
        assert state["max"] == 1, f"{state['max']} requests were inside the models at once"
    finally:
        sys.modules.pop("service.engine", None)
        if saved is not None:
            sys.modules["pipeline"] = saved
        else:
            sys.modules.pop("pipeline", None)


def test_the_request_log_cannot_grow_forever():
    tmp = tempfile.mkdtemp(); path = os.path.join(tmp, "log.jsonl")
    m = Monitor(path, keep=20, max_bytes=4000)                            # 20 rows are about 3 KB, so they fit under the 4 KB cap
    for i in range(400):
        m.record({"id": f"r{i:04d}", "ok": True, "latency_ms": 100, "slots": [{"slot": "front", "check": "match", "verdicts": ["unsure"]}]})
    assert os.path.getsize(path) <= 4000 + 300, os.path.getsize(path)     # 400 rows were written, the file stayed small
    lines = [json.loads(x) for x in open(path, encoding="utf-8") if x.strip()]
    assert lines[-1]["id"] == "r0399" and 20 <= len(lines) <= 40, len(lines)   # the newest rows survive
    assert not os.path.exists(path + ".tmp")
    assert Monitor(path, keep=20).stats()["requests"] > 0                 # and the shortened file can still be read back


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print("  ok  " + t.__name__)
    print("security tests passed (%d)" % len(tests))


if __name__ == "__main__":
    main()
