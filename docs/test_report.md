# Test report (version 1.1.0, 2026-11-12)

What was tested, what passed, and what was **not** tested. Nothing here is estimated.

## Automatic tests (run in the test environment, no GPU, no PyTorch)
| Suite | What it proves | Result |
|---|---|---|
| `tests/test_verdict.py` | verdict and reliability rules, the "never reassure on a weak photo" rule, blank-photo refusal | passed |
| `tests/test_gate_logic.py` | photo-type (familiarity) gate maths | passed |
| `tests/test_service.py` | API with a fake engine: good photo, wrong-type photo, dark photo, heat map only on request, every input error, missing model, monitoring, samples | passed |
| `tests/test_security.py` (9 tests) | browser protections, no CORS, docs switch, real file type, oversized and length-less uploads, pixel bomb, photos stay in memory and out of the log, a crash leaks nothing, path traversal, one request in the models at a time, log size cap | passed |
| `tests/test_web.py` | every text key used by the pages exists in English and Thai, JavaScript parses, local links and fonts exist, no outside links, no inline style or script (so the pages work under the content policy) | passed |

The memory test was shown to **fail** when the fix is removed, so it can detect the problem it guards against. The service tests also pass on Pillow 13.0.0.

## Browser walkthrough (Chromium, scripted engine, English and Thai)
The real service and website were run with a scripted engine whose scores follow the colour of the uploaded picture (tests only), then driven in a browser at 1440, 820 and 390 px wide.
- Screens covered: home, wrong file type, photos added, loading, results, refused photo, network error with retry, details page, monitoring page.
- No horizontal scrolling at any width. No request to any other website. No content-policy violation. The single console message in each run is the request the test aborted on purpose.
- A wrong file type is explained next to the photo before "Check" is pressed. After a network error the photos are still there and "Try again" works. A server that never answers produces the timeout message after 90 seconds (shortened in the test), keeps the photo and re-enables the button.
- A double click on "Check my photos" sends exactly one request. On a phone-sized screen the check button is on screen as soon as a photo is added.
- Elements marked hidden are really invisible until needed (checked by measurement).
- Keyboard order follows the layout: skip link, brand, menu, language, then the page.
- Every button and link the user taps is at least 44 px tall.
- A 15.1 MB photo (4200 x 3000 pixels, rotated by an EXIF tag, with a hidden location note) was accepted on a phone-sized screen. What was sent: 2.0 MB, 1463 x 2048, upright, no EXIF block, no location note, file name `front.jpg`; the service answered normally. The old version would have refused this photo (over 10 MB).
- Checked over real HTTP with curl: a declared 30 MB upload is refused at once (413) without waiting for the body; a chunked upload with no size gets 411; a text file named `.jpg` gets `unreadable`; a cross-site preflight gets no CORS headers; three path-traversal URLs get 404; the log held only counts.

## Accessibility scan (axe-core, WCAG 2.1 A/AA plus best practices)
17 page states (home, results, details, monitoring; English and Thai; desktop and phone): **no violations** after one contrast fix (a grey note on the green band was 4.09:1; now above 4.5:1).

## Dependency audit
`pip-audit` on your pinned versions found advisories in Pillow, filelock, certifi and setuptools. See `privacy_and_security.md`.

## Real models (your PC, 2026-10-28, before this refinement)
`scripts\run_test_batch.py` on the running server with held-out dataset photos: no wrong answers on 20 front photos and 31 labelled top-of-head checks; the same answer on three repeats; blurry, blank, noise and gradient pictures refused. Front photos of people without hair loss were answered "not sure" because the dataset photos are small and the app never reassures on small photos. That is deliberate caution, and phone photos were not measured.

## NOT tested
- **The real models after this refinement.** The refinement does not touch the models, thresholds or verdict rules, but it was not run against them here. Run `scripts\run_test_batch.py` after installing and compare with the paragraph above.
- Ordinary phone photos (accuracy unknown; `limitations.md`).
- A real phone or its camera, iOS Safari, Firefox, Edge, screen readers (the axe scan is automatic and cannot judge everything).
- Many visitors at once, and any use over a network.
- The effect of shrinking a photo over 9 MB on the models' answers (the service shrinks every photo to 1024 px anyway, but this was not measured), and how Safari on iPhone applies the rotation tag when shrinking.
