# Can the final evaluation reach 30 unsuitable natural scalp photos? (feasibility + supplement plan)
## 1. Evidence so far (scouting, NOT reference labels)
On 2026-11-23 I looked at a random sample of 36 train-split photos (12 per source, seed 7; contact sheets, not saved with labels) and wrote down only rough impressions. This is one non-reference viewer, N = 36: treat it as a warning light, not a measurement.
| Source (test photos) | What the 12 looked like | Rough share likely `unsuitable` or `ambiguous` under the guide |
|---|---|---|
| hairdata (37) | stock-style crown/parting photos; about 4-5 of 12 show a face or forehead, a mirror scene, a side view or hands over much of the hair | about 3-5 of 12 |
| healthy_scalp (68) | overhead shots of whole people in a venue, sideways, head often a small part of the frame, other people/equipment visible | about 4-6 of 12 |
| extra_dandruff (69) | microscope close-ups, all in focus enough to read hairs; 2 duplicate pairs in 12 | about 0-1 of 12 |
Projection to the 174 test photos: roughly 40-50 photos that raters might call unsuitable OR ambiguous, so perhaps 20-30 clearly unsuitable. **R1 (>= 30 consensus-unsuitable) is borderline to likely underpowered.** The real number will come from your own rating of the 36 dev photos (the planned feasibility check), which costs about 10 minutes and uses nothing that leaves the laptop. Also expected: microscope images may be rejected by a VLM as wrong view; that would raise false rejections inside one source (the protocol reports per source, rule R5 and R3 handle it).
The suitability criteria themselves were checked against these photos; four situations were missing and are now rules in `LABELING_GUIDE.md` (rotated pictures, hands in the picture, tiny head in a scene, microscope close-ups).
## 2. If the check says "underpowered" - supplementary data options (nothing downloaded; none verified yet)
- **A. Accept it:** run Experiment 1 as a descriptive pilot (R1 stays unmet, no adoption claim). Honest and cheapest; fine for the paper if clearly labelled.
- **B. Roboflow "HAIR_AND_SCALP_DISEASE"** (Nayab Waris; Roboflow page shows CC BY 4.0): candidate only. Same weakness as the sources you already use: a Roboflow label does not prove the uploader owned the photos. Needs a provenance check of its README and a sample view before any decision.
- **C. Individually licensed photos (e.g. Wikimedia Commons files, each with its own licence and author):** the best provenance because every file states its licence and author, and attribution is possible per image. I could not open Commons from here, so the availability of enough crown/scalp photos is UNVERIFIED. Faces and identifiable people must be avoided.
- **D. Not recommended:** CC0 dermoscopic skin-lesion images (e.g. ISIC 2018 subset): redistributable, but they are skin-lesion microscope pictures, not crown/scalp photos.
- **E. Your own or friends' photos:** the professor requires public datasets for evaluation, so this needs the professor's written approval first.
## 3. How a supplement can be added without contaminating the frozen test set
1. The original frozen files stay untouched: `scalp_test_174.csv` (SHA-256 recorded in `checksums.txt`).
2. The supplement is a separate stratum `D2` from a different source, listed in its own frozen CSV with image IDs, source URL, licence, author, download date and SHA-256, written BEFORE any rating or VLM run.
3. It is never used for training or for tuning prompts, thresholds or the model-choice rule. The classifier and the familiarity gate were built without it, which `gate_overlap_audit.py` can confirm by showing no exact matches.
4. Near-duplicate check of D2 against the train and test photos (same fingerprint method as the gate) before freezing; remove twins.
5. Reporting: D and D2 appear as separate source rows; R1's count may include D2 only if a written protocol amendment (approved by you) is made BEFORE rating; R5 (gain in at least two sources) then counts D2 as one more source.
6. Disjointness is re-verified with `verify_disjoint.py` extended to D2.
