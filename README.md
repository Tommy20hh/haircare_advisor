# Hair & Scalp Care Advisor

Educational screening demo (version 1.1.0), built as a small AI-as-a-Service: a FastAPI back end with a hand-built website (English / Thai).
Two photos (front, top of head) -> plain-language hair-care ideas. **Not medical advice.** Read `docs/limitations.md` first.

## What it does
| Photo | Model | Output | Trained on |
|---|---|---|---|
| Front photo (face + hairline) | `balding` | balding pattern | Kaggle bald-classification (about 9,100 face photos) |
| Top-of-head photo (scalp visible) | `scalp` | dryness, dandruff, low density | Roboflow scalp sets + healthy-scalp images (883 images) |

Four conditions in two MobileNetV2 models (ImageNet transfer learning). Two models because no public dataset carries all
four labels and the two photo types look very different.

**Pipeline (one request):** upload check -> quality flags -> photo-type check (familiarity gate) -> model + stability
test -> verdict per condition (possible / none seen / unsure / unsuitable) + reliability -> rule-based care ideas.
A photo of the wrong type is refused, not judged. Reliability is capped at "limited" while `PHONE_VALIDATED = False`
(`src/settings.py`): nobody has measured the models on ordinary phone photos yet.

## Run it
```powershell
cd C:\Haircare\v4\hair_care_advisor
.\run_server.bat          # then open http://localhost:8000   (API docs: http://localhost:8000/docs)
```
`checkpoints\balding_model.pt` and `checkpoints\scalp_model.pt` must exist. Step-by-step: `docs/YOUR_STEPS.md`.

## Privacy and security (details: `docs/privacy_and_security.md`)
- A photo is read into memory, judged, and forgotten: never written to disk, never logged, no file name kept. The request log holds only counts, verdict keys and timings.
- The pages load nothing from other websites (fonts are served from `web/fonts`), and the service sends a strict content policy and other browser protections.
- An upload is checked by what the file really is (JPEG, PNG or WebP), by size (10 MB) and by pixel count (40 megapixels) before it is decoded.
- An unexpected error returns a short message, never a stack trace or a server path. No accounts, no cookies, no tracking; the only thing the browser stores is the language choice.
- Meant for one computer (`127.0.0.1`). It has no login, no HTTPS and no rate limit, so do not expose it to the internet as it is. `set HAIR_DISABLE_DOCS=1` switches the `/docs` page off.

## API
| Route | Purpose |
|---|---|
| `GET /health` | ready or degraded, model versions, `phone_validated` |
| `POST /predict` | multipart `front` and/or `crown` photo, optional `heatmap=true`; returns verdicts, photo-type check, advice keys, latency |
| `GET /stats` | request counts, share of photos outside the trained type, latency (no photos stored) |
| `GET /samples` | demo photos from `demo_samples/` (the page has no gallery for them; use `test_photos/` for the demo) |
Errors always look like `{"error": {"code": ..., "message": ...}}`: `unsupported_type` 415, `too_large` / `too_many_pixels` 413, `length_required` 411, `unreadable` / `empty_file` / `too_small` / `no_photo` 400, `model_missing` 503, `server_error` 500.

## Where things are
- `service/` FastAPI app: `main.py` routes and upload checks, `schemas.py` Pydantic contracts, `engine.py` model loading,
  `monitor.py` request log (`logs/requests.jsonl`, no photos).
- `web/` the website: `index.html` (home), `check.html` (add photos, analysis, results), `details.html` (model and research), `monitoring.html` (service statistics), `css/site.css` (design tokens at the top), `js/app.js`,
  `fonts/` (self-hosted), `assets/` illustrations, `data/i18n.json` (all EN/TH text), `data/accuracy.json` (numbers shown on the page).
- `src/` models, training, evaluation, calibration, gate, verdict rules, `pipeline.py` (one photo -> verdicts), `settings.py` (every threshold).
- `scripts/` labels, leak audit, gate, experiments, `stamp_artifact.py`, `check_demo_photos.py`, `probe_photos.py`, `run_test_batch.py` (held-out photos through the running server).
- `demo_samples/` free-licence demo photos (see its README). `notebooks/` Kaggle training. `docs/` audits, protocol, model card, limitations.

## Tests (no GPU needed)
```powershell
python tests\test_verdict.py; python tests\test_gate_logic.py; python tests\test_service.py; python tests\test_security.py; python tests\test_web.py
```
`test_service.py` and `test_security.py` use a fake engine (tests only) with the real verdict rules. With the server running, `scripts\run_test_batch.py` sends held-out photos through the real models. Results: `docs/test_report.md`.

## Honest results (details in `docs/experiment_log.md`)
- Near-duplicates leaked into the v3 scalp test set; they are now grouped and the split is leak-free.
- Honest metric = AUROC inside one photo source with a bootstrap interval. Scalp (n = 37 photos; 10 / 16 / 15 positives): dryness 0.80, dandruff 0.88,
  low density 0.82, wide intervals. Balding 0.993, single source (optimistic).
- Pooled scalp numbers are higher only because the model recognises the photo source; do not quote them as accuracy.
- **Not validated on ordinary phone photos.** The app therefore asks for the photo type it was trained on and refuses others.
  A small consented phone set (test only, with the advisor's approval) is the proposed next step.

## Course concepts used
Serving lifecycle and model artifact (`engine.py`, `stamp_artifact.py`), Pydantic validation (`schemas.py`), health/predict
API, plain `def` endpoints for blocking inference, request logging and drift signal (`monitor.py`, `/stats`), cold-start
warm-up, baseline and leakage checks (`docs/`), rule-based care ideas instead of an LLM (auditable, cannot hallucinate).
