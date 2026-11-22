# Experiment 0 - Baseline reproduction report
Hair & Scalp Care Advisor, model 4.1 / app 1.1.0. Date: 2026-11-23. Status: baseline reproduced and PC verification completed (2026-11-23); Experiment 1 not started.

## 1. What was checked
- Architecture: two MobileNetV2 transfer-learning models (`balding`, 1 output, single run; `scalp`, 3 outputs, 5-fold ensemble). 224x224 resize + ImageNet normalisation, sigmoid outputs, thresholds fitted on out-of-fold predictions, uncertainty band +-0.10.
- Deployed checkpoints vs Kaggle checkpoints: all tensor data identical (`checkpoint_info/weights_comparison.md`). File hashes differ (gate stored in deployed file); see `checksums.txt`.
- Test splits frozen in `frozen_lists/` (hashes in `checksums.txt`); verified by `verify_split.py`.
- Data: Kaggle "Bald Classification Dataset" (balding); Roboflow `hairdata`, `dandruff-big-chunks`, `healthy-scalp` (scalp); licences per `docs/dataset_audit.md`.
- Re-ran `src/evaluate.py` on the user's PC with the Kaggle label files. Original outputs preserved in `metrics_original/` (unedited copies of `metrics.json` and `report.txt`; PNG plots remain in `C:\Haircare\exp0_reproduction\`).

## 2. Reproduced metrics (test set, 1000 bootstrap resamples)
| Test | n | Condition | AUROC (95% CI) | Logged |
|---|---|---|---|---|
| Balding | 841 | balding | 0.993 (0.987-0.998) | 0.993 |
| Scalp pooled | 105 / 174 / 105 | dryness / dandruff / low density | 0.939 (0.882-0.982) / 0.991 (0.981-0.998) / 0.946 (0.897-0.979) | same |
| Scalp style-free (`roboflow_hairdata`, 37) | 37 | dryness / dandruff / low density | 0.800 (0.625-0.931) / 0.878 (0.753-0.968) / 0.821 (0.664-0.940) | same |

Balding at threshold 0.43: precision 0.961, recall 0.993, specificity 0.960 (TN 404, FP 17, FN 3, TP 417). Balding comes from a single photo source.
Pooled scalp AUROCs mostly reflect that the sources differ in photo style; the style-free test is the fair estimate.

## 3. Key baseline findings (recorded separately, measured, not tuned)
A. **Hairdata dandruff recall = 0.625** at the existing threshold 0.86 (10 of 16 positives found; 6 missed; precision 0.909; specificity 0.952). Pooled recall at the same threshold: 0.929.
B. **Hairdata calibration error (ECE)**: dryness 0.170, dandruff 0.129, low density 0.224. Calibration made no difference (temperature = 1.00).
C. **Hairdata inconclusive rate**: dryness 13.5%, dandruff 13.5%, low density 10.8% (about 11-14%). Pooled: 4.8% / 4.6% / 3.8%.
D. **Pooled vs style-free**:

| | Pooled AUROC | Style-free AUROC | Pooled ECE | Style-free ECE |
|---|---|---|---|---|
| Dryness | 0.939 | 0.800 | 0.062 | 0.170 |
| Dandruff | 0.991 | 0.878 | 0.021 | 0.129 |
| Low density | 0.946 | 0.821 | 0.087 | 0.224 |

Low-density and dryness recall on hairdata are 0.40 and 0.50. At n=37 the intervals are wide.

## 4. Split reconciliation
See `split_reconciliation.md`. The repo's old `data/scalp_labels.csv` (706/177) differed from the Kaggle file (709/174) in the `split` column only. 142 of the old file's 177 "test" photos are training photos of the shipped scalp model (shown via the out-of-fold file). `data/scalp_labels.csv` now equals the Kaggle file; old copy in `backup/`.

## 5. Environment (measured on the evaluation PC by `record_environment.py`, 2026-11-23 03:1x)
| Item | Measured value |
|---|---|
| Python | 3.14.7 (MSC v.1944, 64 bit), venv `C:\Haircare\hair_care_advisor\venv` |
| OS | Windows 11 (10.0.26300), AMD64 |
| PyTorch / torchvision | 2.15.0+cpu / 0.29.2+cpu (CPU-only build; `cuda_available` = false) |
| Pillow / numpy / pandas / scikit-learn | 13.0.0 / 2.5.4 / 3.1.1 / 1.9.1 |
| FastAPI / uvicorn | 0.162.5 / 0.54.0 |
| CPU | AMD64 Family 25 Model 80; **12 logical CPUs**; torch uses 6 threads. Marketing name NOT readable (`wmic` unavailable on Windows 11). |
| RAM | 15.9 GB |
| GPU | none usable by PyTorch (CPU build). Any integrated GPU not recorded. |
Notes and open items:
- The versions that ran are NOT identical to `requirements.lock.txt` (torch 2.14.0, pillow 12.3.0, numpy 2.5.3, pandas 3.0.6, fastapi 0.162.0). The lock file records what the project asks for; the table above is what is installed now. Whether the baseline metrics were produced with these installed versions is assumed (same venv), not independently proven. The metrics matched the Kaggle log to the printed precision.
- **Two machines (owner's clarification, 2026-11-23):** this PC is the **development/evaluation machine** (the one measured above). The **presentation machine** is a separate laptop ("Tommy's device", Ryzen 3) used to show the professor the app. The earlier "Ryzen 3" statement therefore refers to the presentation laptop and does not conflict with the 12 logical CPUs measured here. The development PC's CPU marketing name is still unread (optional: Task Manager > Performance > CPU).
- **The presentation laptop has NOT been measured.** Its Python/torch versions, RAM, and the app's speed on it are unknown. The 0.11-0.25 s per photo above is from the development PC and must not be quoted as the demo speed. Before the presentation, run the app and `smoke_real_model.py` on that laptop.
- Evaluation device for the 2026-11-23 re-run: CPU (only build installed).
- Seeds: training seed 42 (Kaggle training summary); evaluation bootstrap seed not independently checked.
- Kaggle training run: 5 folds, 30 epochs, lr 0.001, backbone lr 0.0001, strong augmentation, balanced sources, pos_weight cap 5.0, patience 7.

## 6. Reproduction commands (Windows Command Prompt, from the project root)
`python research\exp0\verify_split.py`
`python src\evaluate.py --task scalp --labels data\scalp_labels.csv --img-dir <RAW_ROOT> --checkpoint checkpoints\scalp_model.pt --results-dir <OUT>\scalp`
Add `--only-source roboflow_hairdata` for the style-free run; use `--task balding --labels data\balding_labels.csv --checkpoint checkpoints\balding_model.pt` for balding. The raw-photo folder was `C:\Haircare\kaggle_upload\raw`. The exact original command lines are in the Command Prompt history, not stored here.

## 7. Previous crop experiment (context only)
`focus_check.json`: 37 photos, 34 with a familiar window; full vs focus-crop AUROC on the same 34: dryness 0.808 vs 0.713, dandruff 0.881 vs 0.863, low density 0.806 vs 0.813. Inconclusive for wide framing because the photos were already close-ups. Not re-run.

## 8. PC verification results (pasted by the owner; raw session in `verification_outputs/pc_cmd_session_2026-11-23.txt`)
**Verified (measured on the owner's PC):**
| Check | Result |
|---|---|
| `verify_split.py` | ALL CHECKS PASSED (14 PASS lines): label-file hashes, 883 = 709 + 174, no duplicates, no train/test overlap by file or group, hairdata test 37 (10/16/15 positives), balding test 841, three frozen lists match, 0 missing photos for the 174 scalp and 841 balding test photos. |
| Gate leakage, scalp | 0 exact and 0 near matches between the 174 frozen test photos and the 709-row gate bank (max cosine similarity 0.969, median 0.707; near threshold 0.98, exact 0.9995). Per source: 69 / 68 / 37 test photos, 0 matches each. Control: all 709 train photos match their own bank row as best match; 697 are exact, 12 are close but below 0.9995 (min 0.9988). |
| Gate leakage, balding | 0 exact and 0 near matches among 841 test photos against the 8,253-row bank (max 0.973, median 0.810). Control: 8,253 of 8,253 exact. |
| Real-model smoke test | Both deployed models loaded (0.7 s) and produced verdicts for 3 crown and 3 front photos in 0.11-0.25 s each. This shows the code path runs; it is NOT an accuracy result (2 of the 3 crown photos were training photos). |
| `git diff --stat -- src service web checkpoints` | No change under `src/` or `checkpoints/`. Changed: `service/main.py` (+4 lines) and `web/*.html`, `web/js/app.js` (small edits). For `service/main.py`, `web/js/app.js` and `web/index.html` a comparison with the GitHub copy showed only the stale-cache fix (a `Cache-Control: no-cache` header and a `?v=20261123` URL tag). `check.html`, `details.html`, `monitoring.html` and the tests were not compared line by line. |
**Conclusion that the data support:** the deployed familiarity gates contain no sign of any frozen test photo (exact or near-duplicate at the stated thresholds). Limits: the audit finds duplicates and near-duplicates by an ImageNet-feature fingerprint; it cannot rule out a differently cropped version of the same scene below 0.98 similarity. The 12 scalp control photos below 0.9995 are unexplained; a possible cause (one 108-megapixel image triggered Pillow's decompression-bomb warning and may be resized differently) is a hypothesis, not tested.

## 9. Remaining uncertainties and pending items
- **Earlier approved evaluation: pending verification.** The document was not supplied. Nothing here assumes what it says, or that it approves the two-model architecture.
- **Dataset provenance and licensing are NOT settled** (see `PROVENANCE_EVIDENCE.md`). The CC BY 4.0 notes come from README files of Roboflow exports; they were not checked against the live pages, and a CC label does not prove that the uploader owned each image.
- Development PC CPU name and GPU unrecorded; the presentation laptop (Ryzen 3) is entirely unmeasured (see section 5).
- The 37-photo style-free test has wide intervals; no phone-photo accuracy is measured (`PHONE_VALIDATED=False`).
- The October real-model batch (`test_photos/summary.md`) used rows from the old split; its crown results must not be cited as held-out accuracy (16 of 20 were training photos).
- `scripts/run_test_batch.py` has not been re-run against the corrected file.
- The Roboflow `hairdata` credit in `data/README.md` (`getready/hairdata-nyeix`) differs from the export README (`aungkaung-phyo/hairdata-nyeix-wkpgb`); not changed (see `PROVENANCE_EVIDENCE.md`).
- Visibility of the Kaggle dataset `aungkaungphyo/hair-images-zip` is unchecked.
- Thresholds, weights, verdict logic and the live app were not modified by this research work.
