# Project audit (Stage 1)

> **Historical.** Written on 2026-10-17, before the move from Streamlit to the FastAPI service and the website, so it mentions `app/` and Streamlit. The current audit and change record is `refinement_audit.md`.

Date: 2026-10-17. Scope: all code in `src/`, `scripts/`, `app/`, the label files and the saved v3 results.
"Verified" = I ran or read it myself. "Not run" = could not be executed in my workspace (no PyTorch there).

## Verified findings

| # | Finding | Evidence | Severity | Fix in v4 |
|---|---|---|---|---|
| 1 | **Test leakage in the scalp data.** The extra dandruff set was exported from Roboflow with "3 versions of each source image" (brightness/exposure augmentation). Those copies were split randomly, so a test photo often had a twin in training. 62 of the 71 test photos from that set had a near-identical copy in train/val. | `docs/audit_scalp.json` (perceptual-hash audit, 95 cross-split pairs); dataset README | **High**: inflates the pooled dandruff AUROC (0.994) | Grouped split in `build_labels.py` (`group` column); re-audit shows 0 cross-split pairs (`docs/audit_scalp_after_fix.json`) |
| 2 | **Cross-validation was not grouped**, so OOF predictions, temperature and thresholds were also fitted on leaky folds. | `train.py` `make_folds` (read) | High | `StratifiedGroupKFold` using `group` |
| 3 | **Source shortcut.** Healthy photos are 1280x720 screenshots, condition photos are stock photos (612x408 or 512x512 stretched). Per-source mean probability in v3: healthy 0.03, extra dandruff set 0.99. | v3 `report.txt`, image sizes measured | High | Style-free metric (inside `roboflow_hairdata`), strong augmentation, balanced sources, optional source-blind training |
| 4 | **The extra dandruff set cannot test dandruff vs healthy**: 100% positives. Its 67 images annotated only with class `s` (meaning unknown) are also labelled dandruff by the forced-column rule. | label table, COCO annotation counts | Medium | Reported as a limitation; image `s`-only labels flagged in `dataset_audit.md` |
| 5 | **"dry hair" is not "dry scalp".** The `hairdata` class is named "dry hair"; the app says dry scalp. | COCO categories | Medium | Wording in the app/model card says "dry (hair/scalp)" cannot be separated; limitation |
| 6 | **Dryness and low-density test sets are tiny** (v3: 8 and 13 positives); F1 interval for dryness 0.0 to 0.8. | v3 `metrics.json` | Medium | Reported with intervals; honest metric uses cluster bootstrap |
| 7 | Thresholds/temperature come from OOF predictions of the **training pool**, never the test split. | `train.py` (read) | OK | unchanged |
| 8 | Missing labels are NaN and masked in loss and metrics, not treated as negative. | `dataset.py`, `train.py` (read) | OK | unchanged |
| 9 | Preprocessing in training eval, `evaluate.py` and the app all use the same `EVAL_TRANSFORM` (Resize 224x224 + ImageNet normalisation). | `dataset.py`, `inference.py` (read) | OK | unchanged |
| 10 | Early stopping picks the epoch on the same validation fold that produces the OOF predictions, so OOF scores are slightly optimistic. | `train.py` (read) | Low | Documented; test split stays independent |
| 11 | Balding data: 1 cross-split near-duplicate pair among 9,094 photos. Same-person leakage cannot be checked (no person IDs). | `docs/audit_balding.json` | Low / unknown | Duplicate group moved to one split; limitation stated |
| 12 | **The app showed raw scores, a "decision line" and "Inconclusive", and returned confident "Not detected" for photos unlike the training data.** | Screenshots from the user | High (trust) | Plain-language verdicts, familiarity gate, stability check, never-reassure rule |
| 13 | Scalp model is trained on close-up crops; the crown photos users take are wide, top-down head shots. | Screenshots | High | Familiarity gate + photo guidance (an auto-focus idea was tried and removed, see `experiment_log.md`) |

## Not verified (could not be run here)
- Any PyTorch code: training, evaluation, Grad-CAM, the gate, the stability check and the Streamlit app with real widgets. The code compiles; the pure-Python logic (verdict rules, gate maths, region layout, app flow with a fake Streamlit) passes its tests (`tests/`). The first real run is the Kaggle smoke test.
- Whether ordinary phone photos are handled well. No labelled phone photos exist.

## Recommended order
Run the v4 notebook (leak-free split -> experiments -> gate), copy the checkpoints to the app, test with your own photos and the probe tool, then write the report from `results/`.


## Update: v4.2 architecture
The Streamlit app was replaced by a FastAPI service (`service/`) and a hand-built website (`web/`). Thresholds moved to `src/settings.py`, the decision pipeline to `src/pipeline.py`. `src/recommend.py` (unused) and the auto-focus experiment were removed; see `docs/care_rules.md`.
