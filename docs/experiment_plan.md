# Experiment plan

Question: can the scalp model learn the scalp rather than the photo source?

Fixed: MobileNetV2, 224x224, seed 42, 5-fold grouped CV, same label file, same test split (untouched).
Selection metric (not the test set): mean out-of-fold AUROC *inside roboflow_hairdata* over dryness, dandruff, low density.

| ID | Change vs previous | Hypothesis |
|---|---|---|
| E0 baseline | v3 recipe on the leak-free split | the honest starting point |
| E1 strong aug | grayscale, JPEG quality, down/up-sampling, noise, stronger colour | removes colour/compression/resolution cues |
| E2 balanced | each source supplies equal share of each batch | small but informative source is not drowned out |
| E3 source-blind | reversed-gradient source guesser | features carry less source information |

Balding: B0 standard vs B1 strong, chosen by validation log-loss.

Then: evaluate E0 and the winner once on the test split; build the familiarity gate; check whether judging only familiar-looking windows ("auto-focus") beats the full photo. It did not, so it was removed from the app.

Success is **not** "higher number". Success is a style-free AUROC with an honest confidence interval, and an app that says "not sure" when it should.
