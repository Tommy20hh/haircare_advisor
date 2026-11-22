# Decision log: two-model rebuild (v3)

| Decision | Why |
|---|---|
| Split into a balding model and a scalp model | v2 mixed Kaggle face portraits and Roboflow scalp close-ups into one 4-output model and filled the unassessed columns with 0. The photo type then revealed the label, so some of the accuracy came from recognising the dataset, and a normal selfie matched neither. |
| Unknown labels are NaN, masked in loss and metrics | "Not annotated" is not "absent". The extra dandruff-only set therefore trains dandruff only. |
| Added healthy-scalp images | Only 6 of 186 original Roboflow images had no condition, so the scalp model barely saw normal scalps (cause of confident false positives). |
| Dropped images annotated only with other conditions | We cannot know if an alopecia/psoriasis/grey-hair image also has dryness etc. |
| De-duplicate by iStock id then md5 | Different Roboflow exports reuse the same stock photos; duplicates across train/test inflate results. |
| Two-stage fine-tuning, augmentation | Small data: protect pretrained features first, then adapt; augmentation reduces reliance on photo style. |
| 5-fold CV + ensemble for scalp | A single split with ~10 test positives per class is too noisy. |
| pos_weight capped at 5 (was 50) | 50x pushed the model to over-predict and be over-confident. Mild weighting plus tuned thresholds is cleaner. |
| Temperature calibration + per-class thresholds on out-of-fold data | So a displayed 0.80 means roughly 80%, and thresholds are not blindly 0.5. Test data never used for tuning. |
| Report AUROC, bootstrap CIs, ECE, selective accuracy, per-source table | Honest on small data; exposes source-shortcut risk. |

Known open risks: healthy images from a different source may still differ in style; balding data skew; no clinical ground truth.
