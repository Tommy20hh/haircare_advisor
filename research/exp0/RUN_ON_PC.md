# Remaining Experiment 0 checks - run on your Windows laptop (Command Prompt, copy/paste each block)
Paths below were checked on your PC: project `C:\Haircare\v4\hair_care_advisor`, photos `C:\Haircare\kaggle_upload\raw`, Python `C:\Haircare\hair_care_advisor\venv\Scripts\python.exe` (the one `run_server.bat` uses). The raw folder contains `balding`, `dryness_dandruff`, `extra_scalp`, `healthy_scalp`. All 841 frozen balding-test photos and all 69 frozen extra-dandruff test photos were confirmed present; the script below checks the rest.
Stop the web server first (close its window) so the CPU is free.

```
cd /d C:\Haircare\v4\hair_care_advisor
set PY=C:\Haircare\hair_care_advisor\venv\Scripts\python.exe
"%PY%" research\exp0\verify_split.py C:\Haircare\kaggle_upload\raw
"%PY%" research\exp0\record_environment.py
"%PY%" research\exp0\gate_overlap_audit.py --task scalp --labels data\scalp_labels.csv --img-dir C:\Haircare\kaggle_upload\raw --checkpoint checkpoints\scalp_model.pt
"%PY%" research\exp0\smoke_real_model.py --raw C:\Haircare\kaggle_upload\raw
git status --short
git diff --stat -- src service web checkpoints
```
Then, last, the long one (about 9,000 photos on CPU; probably 5-15 minutes on a Ryzen 3; leave the window open):
```
"%PY%" research\exp0\gate_overlap_audit.py --task balding --labels data\balding_labels.csv --img-dir C:\Haircare\kaggle_upload\raw --checkpoint checkpoints\balding_model.pt
```
What good output looks like: every line of `verify_split.py` says PASS; the scalp audit prints `"exact_matches"` for the test photos and a `control` block where `argmax_equals_own_row` equals 709; `smoke_real_model.py` prints 6 cases with a status; `git status` shows no changes under `checkpoints`, `src`, `service`, `web` other than ones you already know about (the new `research\` folder and `data\scalp_labels.csv` are expected).
If a command fails, paste the last 15 lines. Nothing here changes the app.
