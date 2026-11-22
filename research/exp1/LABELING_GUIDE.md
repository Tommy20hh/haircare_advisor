# Rating guide: is this a suitable crown/scalp photo?
For raters. You will see photos with random ID names. You are NOT told where a photo came from or what condition it has. Rate each photo on its own, alone (do not talk to the other rater until both of you finish).

Question: could a scalp-checking app reasonably analyse this photo? Judge only the photo, not the person.

## Labels
- **suitable** - ALL true: (1) view of the top/crown or a close-up of scalp skin and hair roots; (2) bare scalp or hair parting clearly visible over a meaningful part of the picture (roughly a third or more); (3) in focus - you can tell hair strands and skin texture apart; (4) readable lighting - no big area too dark, washed out or glared; (5) nothing hides the scalp (hat, hand, comb, product, text); (6) one real photograph of one head.
- **unsuitable** - at least one of the six clearly fails. Choose the ONE main reason:
  - `wrong_view` (face, profile, back/side of head only, whole body, scene)
  - `scalp_not_visible_or_too_small` (too far away, hair covers everything, scalp tiny in the frame)
  - `blurry`
  - `too_dark_or_bright`
  - `obstructed`
  - `not_a_photo_or_multiple` (drawing, screenshot, collage, several heads)
- **ambiguous** - you honestly cannot decide, or one rule is borderline (for example scalp visible but only about a quarter of the picture). Use it when needed; do not guess. Add a note saying why.

## Special cases (decided after a first look at the three photo sources - apply them exactly)
- **Rotated pictures** (head sideways or upside-down): orientation is NOT a failure. Judge as if upright.
- **Hands, comb or fingers parting the hair:** if the scalp or parting is still clearly visible over a meaningful area, it is still `suitable` (note `hands`). If they hide most of it, `obstructed`.
- **Face, forehead, mirror, or side view dominates and little scalp shows:** `wrong_view` (or `ambiguous` if it is close to the one-third guide).
- **Whole person or a room visible, head small in the frame:** `scalp_not_visible_or_too_small` (or `ambiguous` if borderline).
- **Microscope/dermatoscope extreme close-ups** (single hairs and skin flakes fill the frame): rate them by the same six rules and ALWAYS add the note `micro`. They are reported as their own group, because ordinary phone photos will never look like this.
- **Several near-identical pictures:** rate each one on its own.

## How to fill the sheet
One row per photo. Columns: `stim_id` (already filled), `label` (suitable / unsuitable / ambiguous), `failure_category` (one of the six words above for unsuitable; `none` for suitable; your best guess or blank for ambiguous), `notes` (optional).
Work in the order given. Do not change earlier answers after seeing later photos. Save as CSV.

## After both raters finish
Agreement is measured (Cohen's kappa). Photos where you disagree are discussed together once; the agreed result is recorded as `adjudicated`. If you still disagree, the photo becomes `ambiguous`. All of this is saved so it can be reported honestly.
