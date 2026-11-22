"""
Hair & Scalp Care Advisor - web service.

    uvicorn service.main:app --port 8000      (see run_server.bat)

One process serves both the API and the website, so the page and the API share an origin
(no CORS settings needed). Interactive API docs: /docs.

    GET  /health            readiness + model versions
    POST /predict           multipart: front and/or crown photo (+ heatmap=true)
    GET  /stats             request statistics for monitoring (no photos are stored)
    GET  /samples[/{name}]  demo photos from the demo_samples folder
    GET  /                  the website (web/)

Blocking work (model inference) lives in plain `def` endpoints, so FastAPI runs them in a worker
thread and the server stays responsive.

Privacy and safety built in (each one has a test in tests/test_service.py):
  - photos are read into memory, never written to disk, never logged, and forgotten after the answer;
  - an upload is checked by what the file REALLY is (not only by what the browser says), by size and by pixel count;
  - every response carries browser protections (security headers + a strict content policy);
  - an unexpected error returns a short JSON message, never a stack trace or a file path.
Set HAIR_DISABLE_DOCS=1 to switch the /docs page off.
"""

import json
import logging
import os
import sys
import time
import uuid
from io import BytesIO
from typing import List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

from fastapi import FastAPI, File, Form, Request, UploadFile  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from PIL import Image, ImageOps, UnidentifiedImageError  # noqa: E402
from starlette.formparsers import MultiPartParser  # noqa: E402

import verdict as verdict_rules  # noqa: E402
from service.monitor import Monitor  # noqa: E402
from service.schemas import ErrorBody, Health, ModelInfo, PredictResponse  # noqa: E402
from settings import (ALLOWED_FORMATS, ALLOWED_TYPES, APP_VERSION, MAX_IMAGE_PIXELS,  # noqa: E402
                      MAX_REQUEST_BYTES, MAX_UPLOAD_BYTES, MAX_UPLOAD_SIDE, MIN_UPLOAD_SIDE, SLOTS)
from verdict import advice_keys  # noqa: E402

SAMPLE_EXT = (".jpg", ".jpeg", ".png", ".webp")
log = logging.getLogger("hair_advisor")

# Starlette keeps an uploaded file in memory only up to 1 MB and then spills it to a temporary file on disk.
# A phone photo is usually bigger than that, so raise the limit above our own upload limit: photos stay in memory.
MultiPartParser.spool_max_size = MAX_UPLOAD_BYTES + 1024 * 1024

# Browser protections for every page this service serves. Fonts, scripts and styles all come from this server;
# the pages contact no other website. /docs (Swagger UI) loads its viewer from a public CDN, so it is the one
# place the strict policy is not applied.
CSP = ("default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; font-src 'self'; "
       "connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "camera=(self), microphone=(), geolocation=(), payment=()",
}
NO_CSP_PATHS = ("/docs", "/openapi.json")
NO_STORE_PATHS = ("/predict", "/health", "/stats")   # answers (and heat maps) must never sit in a browser cache


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


def read_photo(upload: UploadFile) -> Image.Image:
    """Validate and open one uploaded photo. Raises ApiError with a message the user can act on.

    The browser's claim about the file type is only a quick first filter; what counts is the file itself
    (its real format, its size in bytes and its pixel count, all checked BEFORE the picture is decoded)."""
    if upload.content_type not in ALLOWED_TYPES:
        raise ApiError(415, "unsupported_type", "Use a JPG, PNG or WebP photo.")
    data = upload.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise ApiError(413, "too_large", f"The photo is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    if not data:
        raise ApiError(400, "empty_file", "The file is empty.")
    try:
        opened = Image.open(BytesIO(data))            # reads the header only
        if opened.format not in ALLOWED_FORMATS:
            raise ApiError(415, "unsupported_type", "Use a JPG, PNG or WebP photo.")
        if opened.size[0] * opened.size[1] > MAX_IMAGE_PIXELS:
            raise ApiError(413, "too_many_pixels", "The photo has too many pixels. Use a smaller one.")
        image = ImageOps.exif_transpose(opened).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise ApiError(400, "unreadable", "This file could not be read as a photo.")
    if min(image.size) < MIN_UPLOAD_SIDE:
        raise ApiError(400, "too_small", f"The photo is too small (shorter side under {MIN_UPLOAD_SIDE} px).")
    image.thumbnail((MAX_UPLOAD_SIDE, MAX_UPLOAD_SIDE))
    return image


def create_app(engine, log_path: Optional[str] = None, samples_dir: Optional[str] = None) -> FastAPI:
    docs_on = os.environ.get("HAIR_DISABLE_DOCS") != "1"
    app = FastAPI(title="Hair & Scalp Care Advisor API", version=APP_VERSION,
                  description="Educational demo, not medical advice. Photos are analysed in memory and never stored.",
                  docs_url="/docs" if docs_on else None, redoc_url=None, openapi_url="/openapi.json" if docs_on else None)
    monitor = Monitor(log_path)
    samples_dir = samples_dir or os.path.join(ROOT, "demo_samples")
    web_dir = os.path.join(ROOT, "web")

    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError):
        body = ErrorBody(code=exc.code, message=exc.message, request_id=getattr(request.state, "rid", None))
        return JSONResponse(status_code=exc.status, content={"error": body.model_dump()})

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        body = ErrorBody(code="bad_request", message="The request was not understood.")
        return JSONResponse(status_code=422, content={"error": body.model_dump()})

    def _reject(request: Request, status: int, code: str, message: str) -> JSONResponse:
        body = ErrorBody(code=code, message=message, request_id=request.state.rid)
        response = JSONResponse(status_code=status, content={"error": body.model_dump()})
        for k, v in SECURITY_HEADERS.items():
            response.headers[k] = v
        return response

    @app.middleware("http")
    async def protect(request: Request, call_next):
        request.state.rid = uuid.uuid4().hex[:12]
        if request.method == "POST":
            # Refuse an oversized (or length-less) upload before a single byte of it is read.
            declared = request.headers.get("content-length")
            if declared is None:
                return _reject(request, 411, "length_required", "The upload must declare its size.")
            try:
                too_big = int(declared) > MAX_REQUEST_BYTES
            except ValueError:
                too_big = True
            if too_big:
                return _reject(request, 413, "too_large", "The upload is too large.")
        try:
            response = await call_next(request)
        except Exception:
            # Caught here (not by a global handler) so that even a crash gets the security headers below.
            log.exception("unexpected error")       # details stay in the server console; the user sees a short message
            body = ErrorBody(code="server_error", message="Something went wrong on the server.", request_id=request.state.rid)
            response = JSONResponse(status_code=500, content={"error": body.model_dump()})
        for k, v in SECURITY_HEADERS.items():
            response.headers[k] = v
        if request.url.path not in NO_CSP_PATHS:
            response.headers["Content-Security-Policy"] = CSP
        if request.url.path in NO_STORE_PATHS:
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/health", response_model=Health)
    def health():
        models = [ModelInfo(**m) for m in engine.models()]
        ok = all(m.loaded for m in models)
        return Health(status="ok" if ok else "degraded", app_version=APP_VERSION,
                      phone_validated=verdict_rules.PHONE_VALIDATED, models=models)

    @app.post("/predict", response_model=PredictResponse)
    def predict(request: Request, front: Optional[UploadFile] = File(None), crown: Optional[UploadFile] = File(None),
                heatmap: bool = Form(False)):
        t0 = time.perf_counter()
        rid = request.state.rid
        try:
            files = {"front": front, "crown": crown}
            files = {k: v for k, v in files.items() if v is not None and (v.filename or "") != ""}
            if not files:
                raise ApiError(400, "no_photo", "Add at least one photo.")
            images = {slot: read_photo(f) for slot, f in files.items()}
            for slot in images:
                if not engine.has(slot):
                    raise ApiError(503, "model_missing", f"The model for the {slot} photo is not loaded on the server.")

            slots, verdicts, not_assessed = [], {}, []
            for slot, spec in SLOTS.items():
                if slot not in images:
                    not_assessed += spec["conditions"]
                    continue
                image = images[slot]
                out = engine.assess(slot, image)
                fam = out["fam"] or {}
                conds = []
                for name, v in out["verdicts"].items():
                    info = (out["results"] or {}).get(name, {})
                    hm = None
                    if heatmap and v["verdict"] == "possible":
                        try:
                            hm = engine.heatmap(slot, image, name)
                        except Exception:
                            hm = None
                    verdicts[name] = v
                    conds.append({"condition": name, **v, "probability": info.get("prob"), "threshold": info.get("threshold"),
                                  "spread": info.get("spread"), "views_positive": info.get("views_positive"),
                                  "n_views": info.get("n_views"), "heatmap": hm})
                slots.append({"slot": slot, "conditions": conds, "check": {
                    "status": out["status"], "tier": out["tier"], "distance": fam.get("distance"),
                    "familiar_max": fam.get("familiar_max"), "unfamiliar_max": fam.get("unfamiliar_max"),
                    "flags": out["flags"], "width": image.size[0], "height": image.size[1]}})

            latency = int((time.perf_counter() - t0) * 1000)
            resp = PredictResponse(
                request_id=rid, app_version=APP_VERSION,
                model_versions={m["slot"]: m["model_version"] or "unknown" for m in engine.models() if m["slot"] in images},
                phone_validated=verdict_rules.PHONE_VALIDATED, slots=slots, not_assessed=not_assessed,
                advice=advice_keys(verdicts, not_assessed), latency_ms=latency)
            # Audit trail (lecture 1, "Auditable"): which model version answered, how sure it was, how long it took.
            # Still no photo, no file name: only keys, numbers and timings.
            monitor.record({"id": rid, "ok": True, "latency_ms": latency, "app_version": APP_VERSION,
                            "model_versions": resp.model_versions, "slots": [
                {"slot": s["slot"], "check": s["check"]["status"], "verdicts": [c["verdict"] for c in s["conditions"]],
                 "confidence": {c["condition"]: c["probability"] for c in s["conditions"]}} for s in slots]})
            return resp
        except ApiError as e:
            monitor.record({"id": rid, "ok": False, "code": e.code})
            raise
        except Exception:
            monitor.record({"id": rid, "ok": False, "code": "server_error"})
            raise

    @app.get("/stats")
    def stats():
        return monitor.stats()

    def _manifest() -> dict:
        path = os.path.join(samples_dir, "manifest.json")
        try:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return {}

    @app.get("/samples")
    def samples():
        if not os.path.isdir(samples_dir):
            return {"items": []}
        meta = _manifest()
        items = []
        for name in sorted(os.listdir(samples_dir)):
            if name.lower().endswith(SAMPLE_EXT):
                m = meta.get(name, {})
                items.append({"name": name, "slot": m.get("slot") or ("front" if name.lower().startswith("front") else "crown"),
                              "label": m.get("label", ""), "source": m.get("source", ""), "licence": m.get("licence", "")})
        return {"items": items}

    @app.get("/samples/{name}")
    def sample(name: str):
        path = os.path.join(samples_dir, os.path.basename(name))
        if os.path.basename(name) != name or not name.lower().endswith(SAMPLE_EXT) or not os.path.isfile(path):
            raise ApiError(404, "not_found", "No such sample photo.")
        return FileResponse(path)

    if os.path.isdir(web_dir):
        app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
    return app


def build_default_app() -> FastAPI:
    from service.engine import Engine  # torch is imported only when running for real
    engine = Engine(os.environ.get("CHECKPOINT_DIR", os.path.join(ROOT, "checkpoints")))
    engine.warm_up()
    return create_app(engine, log_path=os.path.join(ROOT, "logs", "requests.jsonl"))


def __getattr__(name):  # `uvicorn service.main:app` builds the real app lazily, so tests can import this module
    if name == "app":
        return build_default_app()
    raise AttributeError(name)
