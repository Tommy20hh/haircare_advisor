# Run on the development PC - Command Prompt (not PowerShell)
Closes nothing and changes nothing in the app. Writes only inside `research\exp1\stimuli\` and `research\exp1\private\` (both ignored by git).
```
cd /d C:\Haircare\v4\hair_care_advisor
set PY=C:\Haircare\hair_care_advisor\venv\Scripts\python.exe
"%PY%" research\exp1\verify_disjoint.py --simulate
"%PY%" research\exp1\build_stimuli.py --raw C:\Haircare\kaggle_upload\raw
"%PY%" research\exp1\verify_disjoint.py
git status --short
git check-ignore -v research/exp1/stimuli/dev/x.jpg research/exp1/private/rate_dev_rater1.html
```
Good output: the first command ends `ALL CHECKS PASSED`; the second prints `final_natural 0 | dev natural 36 | dev synthetic 0` (and one PillowDeprecation/"DecompressionBombWarning" line is harmless); the third prints 12 PASS lines and `ALL CHECKS PASSED`; `git status` shows NO line mentioning `stimuli` or `private`; `git check-ignore` prints two lines starting `.gitignore:20:` and `.gitignore:21:`.
Then do the rating (RATING_GUIDE.md) and run:
```
"%PY%" research\exp1\dev_feasibility.py
```
