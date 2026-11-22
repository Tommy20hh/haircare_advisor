# Dataset audit

| Source | Role | Images used | Original format | Licence | Labels |
|---|---|---|---|---|---|
| Kaggle bald classification ("balding/Dataset") | Front-photo model | 9,094 (balanced 4,547 / 4,547) after balancing NotBald | Face photos, variable size | See the Kaggle page (not stored in the files; check before publishing) | Bald / NotBald (image level) |
| Roboflow `hairdata` (project of Roboflow user aungkaung-phyo, hairdata-nyeix-wkpgb) | Scalp model: dryness, dandruff, low density | 180 (6 dropped) | iStock-style stock photos, ~612x408 | CC BY 4.0 | COCO boxes: dandruff, dry hair, low hair density (+ grey hair, ignored) |
| Roboflow `dandruff-big-chunks` (scalpdet) | Scalp model: dandruff positives only | 353 (17 dropped) | 512x512 **stretched**, Roboflow augmentation x3 | CC BY 4.0 | COCO boxes `dc` (dandruff chunks) and `s` (meaning unknown) |
| Roboflow `healthy-scalp` (defaultworkspace-c3ew1) | Scalp model: confirmed healthy negatives | 350 of 515 | 1280x720 **screen captures** | CC BY 4.0 | "Healthy Scalp" |

Attribution is required for the CC BY 4.0 sets; list them in the report.

## Source x label (scalp, after the v4 grouped split)

| Source | n (train / test) | dryness | dandruff | low density |
|---|---|---|---|---|
| roboflow_hairdata | 180 (143 / 37) | 48 pos / 132 neg | 94 pos / 86 neg | 61 pos / 119 neg |
| extra_dandruff_big_chunks | 353 (284 / 69) | unknown | 353 pos / 0 neg | unknown |
| healthy_scalp | 350 (282 / 68) | 350 neg | 350 neg | 350 neg |

Only `roboflow_hairdata` contains both positives and negatives for every condition. It is the **only** place a style-free test is possible. Its test part: 37 photos (dryness 10 pos, dandruff 16 pos, low density 15 pos), as in `experiment_log.md`. (An earlier version of this file said 36 photos and 19 / 12 positives; the experiment log is the record of the real run.)

**Split provenance (Experiment 0, 2026-11).** `data/scalp_labels.csv` is the label file saved with the Kaggle run outputs that produced the shipped scalp model (its 709 train rows are exactly the 709 rows of that run's out-of-fold predictions): 883 photos, 709 train / 174 test (SHA-256 `e0390abb...`). Until Experiment 0 this repository held a different copy (706 / 177, SHA-256 `8812e37b...`; hairdata test 36 instead of 37). Same photos, same groups, same labels; only the `split` column differed (281 of 883 photos). The old copy is kept at `research/exp0/backup/`. Details: `research/exp0/split_reconciliation.md`.

## Leakage audit (perceptual hash, difference hash, <=10 of 256 bits)
- Before the fix: 310 near-duplicate pairs; **95 crossed train/test**, all inside the extra dandruff set (62 of its 71 test photos had a twin in train).
- After the fix: 310 pairs, **0 cross-split** (`audit_scalp_after_fix.json`).
- Balding: 18 pairs, 1 cross-split (resolved).
- Not detectable: the same person in different photos.

## Problems that remain
1. **Image style differs per source** (size, aspect ratio, compression, screenshot vs stock). A model can use it. Strong augmentation and balancing reduce it; they cannot remove it. This is why the style-free metric exists.
2. "dry hair" in the source is used as dryness; it may not mean dry scalp.
3. 67 photos in the extra set carry only the unexplained class `s` but are labelled dandruff. Review a sample before the final report; if they are not dandruff, remove them.
4. Very small positive counts for dryness and low density.
5. No phone photographs anywhere in the labelled data.

## Public data worth looking for (not downloaded; check licences first)
Healthy-scalp or "normal" classes inside scalp-disease sets from the same camera as the affected photos; any set with both healthy and affected close-ups from one capture process. Do not mix labels across datasets without a documented rule.
