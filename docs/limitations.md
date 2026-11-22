# Limitations (say these out loud in the report and the demo)

1. Not a medical device. It describes visible patterns in a photo.
2. **Not tested on ordinary phone photos.** All labelled data are stock/close-up or screenshot images. Accuracy on your own head photos is unknown.
3. The style-free scalp test has only 37 photos (10 dryness, 16 dandruff, 15 low-density positives; `experiment_log.md`), so the intervals are wide. The balding result comes from a single photo source.
4. Dryness and low density have few positive examples.
5. "Dry hair" labels may not mean dry scalp.
6. A low score does not prove that a condition is absent; the app avoids reassuring answers on weak photos.
7. The familiarity gate and stability check are safety nets, not proven accuracy improvements. An "auto-focus" idea (judging only familiar-looking windows of a wide photo) was tested, gave no measurable benefit, and was removed (see `experiment_log.md`).
8. Grad-CAM heat maps show influence on the score, not correct reasoning.
9. Same-person leakage across splits could not be checked.
10. The app is meant for one computer. It has no login, no HTTPS and no rate limit, so it must not be exposed to the internet as it is (`privacy_and_security.md`).
11. A photo larger than 9 MB is scaled down on the phone before it is sent (so it is not refused). Smaller photos are sent untouched. Tested in a desktop browser (size, rotation and removal of location data); its effect on the models was not measured, and the service shrinks every photo to 1024 px anyway.
