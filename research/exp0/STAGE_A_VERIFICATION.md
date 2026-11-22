# Stage A verification report (2026-11-23)
| Item | Result |
|---|---|
| Corrected split verification | PASSED on the owner's PC, 2026-11-23 (14 checks incl. all frozen photos present) |
| Frozen test lists | PASSED (hashes in `checksums.txt` match the PC copies) |
| Deployed checkpoints unchanged | PASSED: SHA-256 re-read from the PC on 2026-11-23 equals the Experiment 0 record (balding 6d1fff44..., scalp f0bba89e...) |
| Gate sizes vs frozen split | PASSED structurally: scalp gate 709 rows = 709 train rows; balding gate 8,253 = 7,312 train + 941 val; no test rows by construction of `build_gate.py` |
| Per-photo gate overlap counts | VERIFIED on the PC: scalp 0/174 and balding 0/841 exact or near matches (see EXPERIMENT0_REPORT section 8) |
| Installed versions and hardware | VERIFIED versions and RAM (15.9 GB, 12 logical CPUs, CPU-only torch). CPU marketing name unresolved: stated "Ryzen 3" does not fit 12 logical CPUs; read it from Task Manager |
| Real-model smoke test | PASSED: 6 photos assessed by the deployed models (code path only, not accuracy) |
| Accidental production changes | Checkpoints and `src/`: none. `service/main.py`, `web/index.html`, `web/js/app.js` differ from GitHub only by the stale-cache fix (compared line by line); other web pages and tests not compared line by line |
| Provenance uncertainty remaining | Roboflow `hairdata` credit wording unconfirmed; how the old repo split came to exist unknown; the October crown test used the old split; earlier approved evaluation not supplied |
PC checks are complete. Provenance/licensing is unresolved (PROVENANCE_EVIDENCE.md). No VLM execution, upload or image generation until the owner approves.
