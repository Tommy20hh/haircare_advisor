# Data setup (v3: two models, nothing forced)

Public datasets only, no personal data. Put everything under ONE folder (the "raw root"), then zip that
folder and upload it to Kaggle as a Dataset.

```
raw/
  balding/Dataset/{Train,Validation,Test}/{Bald,NotBald}/*.jpg       <- required
  dryness_dandruff/{train,valid,test}/_annotations.coco.json + imgs  <- required
  healthy_scalp/**/*.jpg                                             <- strongly recommended
  extra_scalp/dandruff_big_chunks/{train,valid,test}/...             <- optional
```

| Folder | Source | Used for |
|---|---|---|
| `balding/` | Kaggle "Bald Classification Dataset" (Ashish Jangra) - face photos | balding model |
| `dryness_dandruff/` | Roboflow `getready/hairdata-nyeix`, export **COCO** | scalp model (dryness, dandruff, low density) |
| `healthy_scalp/` | Roboflow `defaultworkspace-c3ew1/healthy-scalp-p2ire` (515 images, CC BY 4.0). Export any format, then copy all the images (train/valid/test together) into this folder | scalp model: confirmed-healthy examples |
| `extra_scalp/<name>/` | Roboflow `scalpdet/dandruff-big-chunks` (CC BY 4.0), export **COCO** | scalp model: more dandruff |

Note: the scalp model's training photos are close-ups of the scalp, so ask users for a close crown photo with the scalp visible, not a distant shot of the whole head.

Why `healthy_scalp/` matters: the original Roboflow export has only 6 images with no condition, so a model trained on it
alone has almost never seen a normal scalp and over-reports conditions. These images fix that.

For a set whose class name does not mention "dandruff" (e.g. "big chunks"), create a one-line text file
`extra_scalp/<name>/_column.txt` containing `dandruff` so every annotation counts as dandruff.

## Build the label files

```bash
python scripts/build_labels.py --raw-root /path/to/raw --out-dir data
```

Writes `balding_labels.csv` and `scalp_labels.csv`. Rules (also in the script):

- A condition a dataset never annotated is left **empty (unknown)**, never filled with 0. The training loss and the
  metrics skip unknown cells.
- Healthy-scalp photos are confirmed negatives for all three scalp conditions.
- A scalp image annotated only with other conditions (alopecia, psoriasis, grey hair...) is dropped.
- Duplicates across sources are removed (iStock id, then file hash) so one photo cannot be in train and test.
- The scalp test split (20%) is stratified and never used for training, tuning or calibration.

## Check before you trust it
Open a few photos from every source (the notebook shows a grid). If healthy photos look like a completely different kind
of picture than the condition photos, the model may learn the picture style. Note this in your report.

I (the assistant) could not open the real images or verify the framing of the healthy-scalp set, so this check is yours.
