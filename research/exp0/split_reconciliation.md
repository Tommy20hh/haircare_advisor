# Scalp split reconciliation (36 vs 37 hairdata test photos)

Compared: `v4_results/data/scalp_labels.csv` (Kaggle run outputs, SHA-256 e0390abb...bbbb16...)vs the repository's previous `data/scalp_labels.csv` (SHA-256 8812e37b...).

| Check | Result |
|---|---|
| Rows | 883 in both |
| Set of image IDs (`filepath`) | identical; no duplicates in either |
| `group` IDs | identical for every image |
| `source`, `dandruff` labels | identical |
| `dryness`, `low_density` labels | identical (353 apparent differences were empty cells, i.e. unknown labels in the extra-dandruff source; compared as numbers there are 0 differences) |
| `split` column | **differs for 281 of 883 photos** (139 test->train, 142 train->test) |
| Kaggle file: train/test | 709 / 174 (test: 69 extra-dandruff, 68 healthy, 37 hairdata) |
| Old repo file: train/test | 706 / 177 (test: 71 extra-dandruff, 70 healthy, 36 hairdata) |
| Train/test overlap, either file | none by image ID and none by group |

## What was demonstrated about the old file
The Kaggle run's out-of-fold prediction file (`scalp_oof_predictions.csv`) lists exactly the 709 train rows of the Kaggle file, i.e. the photos the shipped scalp model was trained and validated on. Of the 177 photos the old repo file called "test", **142 (56 extra-dandruff, 56 healthy, 30 of 36 hairdata) appear in that training set.**
Consequence: the old file was not the split the model was evaluated on. Any evaluation run against it (for example `scripts/run_test_batch.py` in October) used mostly training photos.

## What was NOT demonstrated
- How the old file came to exist (most likely `build_labels.py` re-run on another machine/environment; not verified).
- That any published metric was computed from the old file. The logged metrics reproduce exactly from the Kaggle file.
- Near-duplicate leakage inside the Kaggle split beyond the logged audit (1 of 174 test photos has a near-twin in training, `experiment_log.md`).

## Action taken
Old file backed up to `research/exp0/backup/`; `data/scalp_labels.csv` replaced with the Kaggle file (byte-identical, SHA-256 in checksums.txt). Not changed: weights, thresholds, verdict logic, the familiarity gate stored inside the checkpoints (it was built from train rows of whichever file was used at the time; not re-checked).
