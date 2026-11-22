# Privacy and security (version 1.1.0)

The app handles photos of people's heads, so this page says exactly what it does with them. Every point marked *(test)* is checked
automatically by `tests/test_security.py`, `tests/test_service.py` or `tests/test_web.py`.

## What happens to a photo
1. The browser sends it to this computer only. The page contacts no other website: fonts, scripts and styles are served from the project itself *(test)*.
2. The service reads it **into memory**. Starlette would normally write uploads over 1 MB to a temporary file on disk; the service raises that limit above its own 10 MB cap so no photo is spilled to disk *(test)*.
3. The photo is judged, the answer is sent back, and the picture is forgotten. Nothing is saved, so there is nothing to look up later and no way for one visitor to see another's photo or result.
4. Heat-map images (only if the box is ticked) are made in memory and sent back in the same answer; they are never stored.
5. The browser keeps the chosen photos only on the open page (as temporary in-page links that are released when a photo is replaced or removed). The only value written to browser storage is the language choice (`en` / `th`).

## What is kept
- `logs/requests.jsonl`: one line per request with a random request id, time, how long it took, the photo-type result, and the verdict keys. **No file name, no pixels, no address, no cookie.** The log is cut back automatically when it passes 2 MB *(test)*.
- The browser's original file name is not even sent: the page uploads each photo under a neutral name (`front.jpg`, `crown.png` and so on).

## Checks on every upload
| Check | Result |
|---|---|
| Real file type (JPEG, PNG, WebP) judged from the file itself, not only the browser's label | `unsupported_type` 415 *(test)* |
| Size over 10 MB | `too_large` 413 *(test)* |
| Whole upload larger than 21 MB, or no declared size, refused before any of it is read | 413 / 411 *(test)* |
| More than 40 megapixels (a tiny file that unpacks into an enormous picture) refused from the header, before decoding | `too_many_pixels` 413 *(test)* |
| Not readable as a picture, or empty, or under 64 px | `unreadable` / `empty_file` / `too_small` 400 *(test)* |

A photo over 9 MB is scaled down **on the phone** before it is sent, so it is not refused. This also removes any location data stored in the original file, because the picture is redrawn as plain pixels. Smaller photos are sent exactly as chosen (the service never stores them, and a location tag would only reach the memory of this one computer).

## Browser protections (sent with every page and answer) *(test)*
- A strict content policy: only this server may supply scripts, styles, fonts and images; no inline script, no inline style; the page cannot be framed (`frame-ancestors 'none'`).
- `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`, and a permissions policy that switches microphone, location and payment off. The camera is allowed for the page itself only (the page does not use it; the phone's camera app is opened by the file picker, and this setting keeps that working). Not checked on a real phone.
- `Cache-Control: no-store` on `/predict`, `/health` and `/stats`, so an answer is never kept in a browser cache.
- No CORS headers: another website cannot call the API from a visitor's browser *(test)*.
- The `/docs` page is the one exception to the content policy, because the Swagger viewer loads from a public CDN. `set HAIR_DISABLE_DOCS=1` before starting the server switches `/docs` and `/openapi.json` off *(test)*.

## Errors
A crash returns `{"error": {"code": "server_error", ...}}` with a request id and nothing else: no stack trace, no file path, no exception text. The details go to the server console only *(test)*. The refusal itself carries the same security headers.

## Other safeguards
- Two requests never run inside the models at the same time (Grad-CAM attaches a hook to the shared model) *(test)*.
- Path traversal on `/samples/...` and on the static files returns 404 *(test)*.
- No secrets, keys or passwords exist in the project (searched in code, pages, docs and scripts). Nothing in the project reads an environment variable except `HAIR_DISABLE_DOCS` and `CHECKPOINT_DIR`.
- `run_server.bat` starts the server on `127.0.0.1` only, without debug or auto-reload.

## Dependencies (audit run on 2026-11-12 with `pip-audit` against your `requirements.lock.txt`)
70 pinned packages were checked.
| Package (pinned) | Known advisories | Fixed in | Why it matters |
|---|---|---|---|
| Pillow 12.3.0 | 40 | 13.0.0 | It opens every uploaded photo. **Upgrade.** |
| filelock | 14 | 4.0.9 / 4.2.1 | Used by PyTorch to download files; not reachable from the web app. |
| certifi | 2 | 2026.10.18 | Certificate list used when packages download. |
| setuptools | 1 | 84.1.0 | Build tool only. |

`requirements.txt` now asks for `Pillow>=13.0.0`. All five test suites pass on Pillow 13.0.0. **Not tested here:** the real models on Pillow 13 (no PyTorch in the test environment). After upgrading, run `scripts\run_test_batch.py` and compare with `test_report.md`. Upgrade commands are in `YOUR_STEPS.md`.

## What is NOT protected (honest list)
- **No login, no HTTPS, no rate limit.** The app is meant for one computer. Do not put it on the internet as it is; anyone who can reach it can use it and read `/stats`.
- For a phone test on your own Wi-Fi, start the server with `--host 0.0.0.0` only for that test, on a network you trust, and stop it afterwards. Traffic is not encrypted.
- The Kaggle bald-photo set contains real faces and its licence says "check before publishing" (`dataset_audit.md`). Do not publish the photos or the project folder with `data/raw`.
- Browser-side checks (file type, size) are for the user's convenience; the service repeats every one of them.
