# Model card

**Models:** two MobileNetV2 classifiers (ImageNet-pretrained, replaced head: Dropout 0.3 + Linear), sigmoid outputs, masked BCE for missing labels.
- `balding` (front photo): 1 output.
- `scalp` (top-of-head close-up): dryness, dandruff, low density. 5-fold grouped ensemble (logits averaged), temperature calibration, F1-tuned thresholds on out-of-fold predictions, inconclusive band +-0.10.

**Intended use:** classroom demo of educational hair-care screening. **Not** for diagnosis or treatment decisions.

**Data:** see `dataset_audit.md`. **Evaluation:** see `evaluation_protocol.md`; final numbers are in `experiment_log.md` and `web/data/accuracy.json` (from the real Kaggle run).

**Extra safeguards in the app:** familiarity gate (kNN cosine distance to training photos using a neutral ImageNet extractor), stability check (4 slight variants of the photo), photo-quality flags, and the rule that a negative result is downgraded to "not sure" when any safeguard fails.

**Known failure modes:** see `limitations.md`.
