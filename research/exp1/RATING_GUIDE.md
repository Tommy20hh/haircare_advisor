# Photo-rating guide (beginner version) - development set, 36 photos
You are helping decide: **is this photo good enough for a scalp-checking app to look at?** You are NOT judging the person, their hair health, or any condition. Only the photo.
The detailed rules are in `LABELING_GUIDE.md`. This page is the short version with examples.

## The three answers
| Answer | Use it when | Example (described in words) |
|---|---|---|
| **suitable** | You can clearly see scalp skin or the hair parting on at least about 1/3 of the picture, it is in focus, lit well, and nothing blocks it. | A top-down photo of a parting with hair strands and skin sharp and clear. A close-up of scalp skin where you can tell each hair root. Hands holding the hair apart, but the parting is still wide open and clear (add note `hands`). A sideways or upside-down picture that is otherwise good (orientation does not matter). |
| **unsuitable** | One clear problem stops the app from seeing the scalp. Pick the main one (list below). | A selfie where the face and forehead fill the picture. A whole person in a room with the head tiny. A picture so blurry you cannot tell hair from skin. A photo so dark you cannot see the scalp. A hand or comb covering most of the head. A collage or screenshot with several images. |
| **ambiguous** | You honestly cannot decide, or one rule is only borderline. Do not guess: choose this and write why in Notes. | Scalp visible but only about 1/4 of the picture. A photo that is slightly soft: not clearly sharp, not clearly blurry. Half in shadow. |

## Main problem (for "unsuitable")
- `wrong_view`: face, side of head, back of head only, whole body or a scene.
- `scalp_not_visible_or_too_small`: too far away, hair covers everything, or the scalp is a tiny part of the picture.
- `blurry`
- `too_dark_or_bright`
- `obstructed`: hand, hat, comb, product or text hides the scalp.
- `not_a_photo_or_multiple`: drawing, screenshot, collage, several heads.
Choose the ONE biggest problem. For suitable photos the page fills in `none` for you.

## Special notes (type them in Notes)
- `micro`: if it is an extreme close-up where single hairs and skin flakes fill the whole picture (like a microscope). Rate it by the same rules.
- `hands`: if hands are in the picture but the scalp is still clearly visible.
- Very similar-looking pictures: rate each one on its own, do not copy your earlier answer.

## How to do the rating (about 10-15 minutes)
1. Sit at the development PC. Open the folder `C:\Haircare\v4\hair_care_advisor\research\exp1\private\`.
2. **Rater 1 (you):** double-click `rate_dev_rater1.html` (it opens in your browser; it works offline and sends nothing anywhere).
3. Look at each photo and click **suitable**, **unsuitable** or **ambiguous**. Choose the main problem if unsuitable. Add a note if needed. Click **Next**.
4. Rate in the order shown. Do not change earlier answers after seeing later photos (the Back button exists only to fix a mis-click).
5. At the end click **Download my ratings (CSV)**. A file `rating_dev_rater1_DONE.csv` appears in your Downloads folder. Move it into the `private` folder (next to `rating_dev_rater1.csv`). Do not edit it.
6. Your progress is saved in the browser, so you can close the page and come back on the same PC and browser.
### Second rater (independent)
- Pick a person who has not seen your answers and with whom you have not discussed the photos (a classmate or friend).
- **Do not send them the photos.** The images are not cleared for sharing (see below). Let them rate **on this PC, sitting with you but not looking at your answers**, using `rate_dev_rater2.html` (it shows the photos in a different order). They download `rating_dev_rater2_DONE.csv` and you move it into `private`.
- Do not discuss any photo until both of you have finished. After that, the feasibility script compares the two files.
- The second rater is only needed for the 36 development photos if you want agreement numbers now. For the planned final test, two raters will be needed (decision later).
## After rating
Run: `"%PY%" research\exp1\dev_feasibility.py` (commands in `RUN_DEV_STAGE.md`) and paste the output to Claude. It tells us whether the 174 test photos probably contain enough unsuitable ones.

## Licence reminder
The photos come from public datasets whose licence and original source are NOT verified (see `exp0\PROVENANCE_EVIDENCE.md`). Having them on this PC for the university project is local research use. It does not mean you may share, upload or publish them. Keep them in the git-ignored folders.
