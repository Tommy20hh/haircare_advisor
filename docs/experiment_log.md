# Experiment log

All numbers below come from the real Kaggle run (v4 notebook, 2026-10-18). Nothing here is estimated.

## Data check
- Scalp leak audit after the grouped split: 1 of 174 test photos still has a near-twin in training (v3: 62 of 71 in one source). Cause: the split used a fast-decoded hash and the audit a full-decoded one; effect is negligible.
- Balding: 0 cross-split near-duplicates.

## Scalp experiments (5-fold grouped, out-of-fold, inside roboflow_hairdata, n=143)
Selection metric = mean of the three AUROCs. Intervals are about +-0.07, so differences below ~0.02 are noise.

| ID | Change | dryness | dandruff | low density | mean | Decision |
|---|---|---|---|---|---|---|
| E0 baseline | standard aug | 0.912 | 0.909 | 0.850 | 0.890 | reference |
| E1 strong aug | + style augmentation | 0.899 | 0.915 | 0.850 | 0.888 | no gain |
| E2 balanced | + equal source share per batch | 0.909 | 0.924 | 0.859 | 0.897 | **picked (tiny, within noise)** |
| E3 source-blind | + reversed-gradient source guesser | 0.840 | 0.925 | 0.837 | 0.867 | rejected (dryness worse) |

Finding: the style-robust training ideas did **not** clearly improve the scalp model. The honest conclusion is that the limit is the data (small `hairdata` set, source confounds), not the training recipe.

## Scalp, held-out test, inside roboflow_hairdata (n=37; 10 / 16 / 15 positives)
| Model | dryness | dandruff | low density |
|---|---|---|---|
| E0 baseline | 0.737 (0.55-0.89) | 0.872 (0.75-0.97) | 0.815 (0.66-0.94) |
| E2 chosen | 0.800 (0.63-0.93) | 0.878 (0.75-0.97) | 0.821 (0.66-0.94) |

Intervals overlap heavily: the test part is only 37 photos.

## Pooled scalp test (optimistic, includes the source shortcut)
E2: dryness 0.939, dandruff 0.991, low density 0.946. Mean predicted dandruff probability per source: extra dandruff set 0.99, healthy 0.04, hairdata 0.48. The model still separates photo sources almost perfectly; that is why these pooled numbers must not be quoted as accuracy.

## Balding
| ID | val log-loss | test AUROC | Decision |
|---|---|---|---|
| B0 standard | 0.0916 | 0.993 (0.987-0.998), F1 0.977 | **picked** |
| B1 strong aug | 0.0933 | not evaluated on test | rejected |

Single source (one Kaggle set), so there is no style-free check; same-person leakage could not be checked.

## Auto-focus check (hairdata test, n=37; 3 photos had no familiar window)
| | full photo | auto-focus (same 34 photos) |
|---|---|---|
| dryness | 0.808 | 0.713 |
| dandruff | 0.881 | 0.863 |
| low density | 0.806 | 0.813 |

Decision: auto-focus gives **no measurable benefit** on this data, so the feature (and its test script) was **removed** from the app and code to keep the system simple. It was never validated on phone photos.
