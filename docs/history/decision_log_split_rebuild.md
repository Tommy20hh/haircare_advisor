# Decision log: train/test split rebuild (2026-09-27)

## Problem
The original `data/labels_test.csv` inherited each source dataset's own
train/test split (kept separate deliberately, to avoid leakage — see
`data/README.md`). The Roboflow "dryness_dandruff" source only put 4 of its
186 images into its own test split, so `evaluate.py`'s reported test metrics
for dryness/dandruff/low_density were based on 1, 3, and 0 positive examples
respectively — not enough to measure anything.

## What changed
- The **balding-source split was left untouched** (421 test positives,
  already reliable — no reason to disturb it).
- Only the 186 **dryness_dandruff-source rows** were re-split: stratified by
  their exact label combination (e.g. "dandruff only", "dryness+low_density"),
  80/20 train/test, seed 42. Groups smaller than 3 rows were kept in train
  (too small to split meaningfully).
- Result: test set now has 9 dryness, 19 dandruff, and 11 low_density
  positive examples (up from 1, 3, 0). Training set still has 39, 75, and 50
  positive examples respectively for those classes.
- Verified: zero filepath overlap and zero duplicates between the new
  trainval/test files (same checks as the original build).

## Files
- `data/labels_trainval.csv` / `data/labels_test.csv` — new split (used by
  train.py / evaluate.py going forward).
- `data/labels_trainval_original_split.csv` / `data/labels_test_original_split.csv`
  — the previous split, kept for reference / reproducibility, not used by
  any script.

## Also changed: `src/train.py`
Added `pos_weight` to `BCEWithLogitsLoss`, computed automatically from the
training split's own class balance (negatives/positives per class, capped at
50x). Balding is ~50% positive so its weight stays ~1x; dryness/dandruff/
low_density are all rare enough that the cap applies (50x). This directly
addresses class imbalance during training, not just at evaluation time —
without it, the loss function barely "noticed" the rare classes' few
positive examples next to balding's abundant ones.

## What this does NOT fix
This does not add any new data — the total number of dryness/dandruff/
low_density images is unchanged (186 total). It fixes (a) how those images
are split, so the model's performance on them can actually be measured, and
(b) how much the loss function weights their positive examples during
training. Whether the resulting precision/recall/F1 numbers turn out strong
or weak, they'll be real numbers based on double-digit test examples per
class instead of near-zero ones.
