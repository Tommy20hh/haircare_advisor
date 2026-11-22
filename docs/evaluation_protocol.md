# Evaluation protocol

1. **Splits.** Near-duplicates are grouped (perceptual hash); a group is never split. Test split is created once and never used for tuning.
2. **Training pool** = train + val rows. Cross-validation is grouped and stratified by source and label pattern.
3. **Temperature and thresholds** are fitted on out-of-fold predictions of the pool only.
4. **Selection** between experiments uses out-of-fold style-free AUROC. Test is looked at for the baseline and the winner only.
5. **Headline metric**: AUROC inside one photo source that has both classes (>=5 of each), with a 95% cluster bootstrap interval (near-duplicate groups resampled together). Pooled AUROC is reported but labelled optimistic.
6. **Also reported**: precision, recall, F1, confusion matrix, calibration error (ECE), inconclusive rate, per-source mean probability (shortcut check).
7. **Never reported**: AUROC when one class is missing; any claim about phone photos (none were tested).
8. **App output** is a verdict, not a probability. Reliability depends on: familiarity of the photo, photo quality, stability under slight changes, and whether the score is close to the threshold.
