# Refinement audit and change record (2026-11-12)

Baseline: the 3 November version (v1.0.0), restored byte for byte. Models, thresholds, verdict rules, datasets and the reported numbers were **not changed**.

## Audit of the baseline
| Question | Finding |
|---|---|
| Working well | Models and verdict logic; honest "not sure" and "can't judge" answers; refusal of wrong and blank photos; nothing stored; JSON errors; English and Thai; four test suites passing. |
| Looked unprofessional | Third menu tab cut off on a phone; three notices stacked above the photo cards; photo actions as small underlined links; the "In short" lines wrapped badly; the results page repeated the same reliability line on every row; spacing and weights were not from one system. |
| Confusing | About 2,000 px of scrolling before "Check my photos" on a phone; the front photo opened the rear camera; a wrong file was only explained after pressing Check; errors were not brought into view and had no retry; no timeout; photos over 10 MB were refused. |
| Technical | The browser's file-type label was trusted; no pixel limit; an unexpected error came back as plain text; two heat-map requests at once could corrupt each other; the request log grew without limit. |
| Privacy and security | **Google Fonts was contacted on every page load.** Photos over 1 MB were written to a temporary file on disk. No security headers or content policy. No upload-size check before reading. Dependencies not audited. |
| Unnecessary or inconsistent | README and `YOUR_STEPS.md` described Docker and a cleanup script that no longer exist; `limitations.md` and `dataset_audit.md` gave 36 test photos where the experiment log says 37; the model card pointed at a `results/` folder that is not in the project; unused sample-gallery code. |

## Changes
**Privacy and security** (`service/main.py`, `service/engine.py`, `service/monitor.py`, `src/settings.py`): self-hosted fonts; security headers and a strict content policy; uploads kept in memory; real-format, size and pixel checks before decoding; a size cap on the whole request; JSON-only crash answers with headers; a lock around the models; a size cap on the log; `no-store` on answers; `HAIR_DISABLE_DOCS`.

**Phone journey** (`web/`): a shorter first screen; one combined notice; photo cards with numbered steps and button-style actions; the check button stays at the bottom of a phone screen once a photo is added; front camera for the front photo and rear camera for the top-of-head photo; the file is checked when chosen, with the message beside the photo; photos over 9 MB are scaled down on the device; a 90-second timeout; "Try again" after a network, timeout or server error; photos kept after any error; "Retake this photo" per photo; a status line while checking (no fake progress); inputs locked while checking so a photo cannot be changed mid-check.

**Results**: reliability shown once per photo when it is the same for every condition; "In short" aligned; one panel per photo instead of one card per row; care ideas as a plain list; the same wording as before.

**Visual system** (`web/css/site.css`): one set of tokens for colour, type, spacing and shape; Fraunces for headings and Noto Serif Thai for Thai headings, Plex for body text, all self-hosted; the same moss and clay identity; contrast checked.

**Documents**: README, `YOUR_STEPS.md`, `limitations.md`, `dataset_audit.md`, `model_card.md` corrected; `privacy_and_security.md`, `test_report.md` and this file added.

**Removed**: the sample-gallery code in `app.js` (the page has no gallery; the `/samples` endpoint remains). New text added: six short interface strings (retry, timeout, server error, too many pixels, "retake this photo", checking hint), in English and Thai.

## Remaining risks and open items
See `privacy_and_security.md` (no login, HTTPS or rate limit; dependency upgrade pending on your PC), `limitations.md` (no phone photos, small test sets) and `test_report.md` (what was not tested).
