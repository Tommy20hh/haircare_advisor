# Your steps (project folder: C:\Haircare\v4\hair_care_advisor)

No retraining is needed. About 30 minutes, plus the demo rehearsal.

## 1. Stop any running server
Click its window and press Ctrl+C, or close it.

## 2. Upgrade the packages that have security advisories (5 min, once)
Pillow opens every uploaded photo, so it matters most (`docs/privacy_and_security.md`).
```powershell
cd C:\Haircare\v4\hair_care_advisor
$py = "C:\Haircare\hair_care_advisor\venv\Scripts\python.exe"
& $py -m pip install -U -r requirements.txt
& $py -m pip install -U certifi setuptools filelock
& $py -m pip freeze | Out-File -Encoding utf8 requirements.lock.txt
```
(`Out-File -Encoding utf8` keeps the lock file readable; plain `>` writes it in a format other tools cannot read.)

## 3. Run the tests (2 min). You should see five "passed" lines
```powershell
& $py tests\test_verdict.py; & $py tests\test_gate_logic.py; & $py tests\test_service.py; & $py tests\test_security.py; & $py tests\test_web.py
```

## 4. Start the website
```powershell
.\run_server.bat
```
Wait about 30 seconds for the models to load. Open http://127.0.0.1:8000 and press Ctrl+F5. The footer shows version 1.1.0 and http://127.0.0.1:8000/health says `"status":"ok"`.
If the window closes at once, run the command inside `run_server.bat` by hand in PowerShell to read the error. `degraded` means a checkpoint is missing from `checkpoints\`.

## 5. Check the real models after the upgrade (3 min)
With the server running, in a second PowerShell window:
```powershell
cd C:\Haircare\v4\hair_care_advisor
& $py scripts\run_test_batch.py
```
Open `test_photos\summary.md`. You should see the same picture as before: no wrong answers, the same answer on repeats, blurry / blank / noise pictures refused, and front photos of people without hair loss answered "not sure" (deliberate caution on small dataset photos). If anything differs, tell me before the demo.

## 6. Rehearse the demo (15 min). Photos are in `test_photos\`
1. **Findings:** `front\front_01_bald.jpg` + `crown\crown_03_dryness.jpg`: "possible" for hairline and dry scalp, with "limited reliability" and the phone-photo note.
2. **Careful behaviour:** `front\front_10_notbald.jpg` + `crown\crown_01_healthy.jpg`: scalp "no clear sign", front "not sure". Explain why before you are asked: the dataset photos are small and the app never reassures from them.
3. **Refusal:** a photo of a room or desk (add 5 of your own to `test_photos\wrong\`), or `wrong\generated_plain_green.jpg`: "can't judge this photo".
4. Open "Why this answer?" and tick the heat-map box once. Press "Retake this photo". Switch to Thai.
5. Show the Model performance and Service monitoring pages and `/docs`.
6. Say the limits out loud (`docs\limitations.md`): not medical advice, not tested on ordinary phone photos, small test sets.
Delete `logs\requests.jsonl` before the real demo so the monitoring page starts at zero.

## 7. Phone test on your own Wi-Fi (optional)
Only on a network you trust, and only for the test: start with `& $py -m uvicorn service.main:app --host 0.0.0.0 --port 8000`, open `http://<your PC's address>:8000` on the phone, then stop the server. Traffic is not encrypted and there is no login (`docs\privacy_and_security.md`).

## 8. Save it with git (so you can always go back)
```powershell
cd C:\Haircare\v4\hair_care_advisor
git status
```
If it says "not a git repository", the repository you used on 3 November is somewhere else: copy this folder's contents into that repository (not its `.git` folder), then run the commands below there.
```powershell
git checkout -b refinement-nov12
git add -A
git commit -m "v1.1.0: privacy and security hardening, phone-first interface, corrected docs"
```
The 3 November commit stays on your original branch, so `git checkout main` takes you back to it. `.gitignore` keeps the models, `test_photos`, logs and backups out of git.

## 9. Tidy up when you are happy
You can delete `cleanup_v44.ps1`, `_after_nov3\` and `_backup_v1.1\` (old copies kept as a safety net).

## 10. Meet the professor
Bring the six questions from the briefing and the demo above. His answers decide whether a small consented phone set is collected, and what the paper claims. After the meeting, tell me and I write the paper (IEEE template, figures below the text that cites them, honest limitations).
