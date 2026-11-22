# Experiment 1 - VLM photo-suitability check for the crown/scalp slot
## PROTOCOL v4 - FINAL TEXT, AWAITING OWNER APPROVAL (not frozen, nothing run)
It is frozen only when the owner approves it and its SHA-256 is written down (command in KAGGLE_GUIDE.md). Sections 6-8 cannot change after that.
Scope: **photo-suitability decisions only.** No claim about condition recognition is made or allowed.

## 1. Question and methods
Can a vision-language model (VLM) improve crown/scalp photo-suitability decisions compared with the app's existing quality and familiarity checks?
- **A. Existing checks** (`src/pipeline.assess`, untouched): A-hard rejects only status `mismatch`; A-strict accepts only status `match`.
- **B. VLM-only**: accept only if valid JSON with `suitable: yes`; `no`, `unsure`, invalid or missing output = refuse / ask for a retake.
- **C. Combined**: accept only if A-x AND B accept. The VLM can only downgrade.
The VLM never diagnoses, never sees classifier output, never raises confidence. The app stays FastAPI + MobileNetV2, works offline, and the presentation never depends on a VLM. Heavy runs are on Kaggle only.

## 2. Suitability definition and raters
See `LABELING_GUIDE.md` (6 criteria; 6 failure categories; `ambiguous` is a real label). Humans label blind (random IDs; no source, condition, classifier or VLM information). Two independent raters (owner + one other person; never Claude). Report Cohen's kappa (3 classes), raw agreement, confusion table, adjudicated count, unresolved count. If kappa < 0.60, results are reported on the agreed subset only and labelled so. Ambiguous photos are excluded from FAR/FRR and reported separately.

## 3. Strata - what can and cannot decide the experiment
| Stratum | Content | Role |
|---|---|---|
| **D - decision stratum** | the 174 frozen scalp-test photos (hairdata 37, healthy-scalp 68, extra-dandruff 69), human-labelled | **The only stratum used in the success rules.** |
| **E - easy wrong-view faces** | OFF by default (see DATA_LICENCE_PRIVACY_REVIEW.md). If the owner later enables N faces, they are reported in their own table as a sanity check | Never in any success rule. Passing E proves nothing about hard crown photos. |
| **T - synthetic stress** | up to 30 originals (both raters: suitable) x 5 degradations x 2 severities = 300 | Technical stress test only; never in any success rule; not evidence for phone photos; moderate severity = dose-response curve, severe = expected unsuitable by construction (20% spot-checked by a human). |
| **Dev set** | 36 scalp-train photos (12 per source) + 16 severe synthetic variants of 4 of them | Prompt tuning and the pilot only. Never reported as a result. |
Disjointness (checked by `verify_disjoint.py`): dev photos are train rows only; final photos are the frozen test list; no photo and no group id is shared; every synthetic variant carries its `original_id` and lives in the same set family as its original; no original feeds both dev and final. Simulated on the real label files on 2026-11-23: 174 final / 36 dev, 0 shared photos, 0 shared groups. Method A is not scored on dev (dev photos are in the gate's bank, so "familiar" by construction). Residual risk: near-duplicate twins across train/test (the earlier audit found 1 of 174 test photos with a near-twin) cannot be excluded from the dev set; it can only affect prompt tuning, not final scoring.
**Supplement rule:** a supplementary public dataset (stratum D2) may be added only through a written amendment approved by the owner before any final rating; see FEASIBILITY_AND_SUPPLEMENT.md. The 174 frozen photos and their hash never change.
**Feasibility check before final rating:** the owner rates the 36 dev scalp photos first. If the share rated unsuitable or ambiguous there, applied to 174, predicts fewer than 30 unsuitable photos in D, the experiment is declared underpowered in advance and a supplementary public dataset (with checked licence and provenance, needing separate approval) is proposed BEFORE final rating. No threshold is relaxed afterwards.

## 4. Information barrier
The VLM receives only the image and `prompts/suitability_v1.txt`. Its inputs: `manifest_public.csv` (stim_id, set, file) and images. Labels, sources, groups, gate tiers, quality flags and classifier outputs exist only in `private/` on the laptop. The prompt names no condition. Greedy decoding, max 60 new tokens, same stimulus bytes for Methods A and B.

## 5. Metrics (all with raw counts, on D unless stated)
FAR (unsuitable accepted / unsuitable), FRR (suitable refused / suitable), precision of refusals, recall (= 1 - FAR), coverage (accepted share), invalid-JSON rate, latency (median, p95), peak GPU memory. By image source and by failure category (a category is interpreted only if it has at least 10 consensus-unsuitable photos; otherwise counts only). Intervals: cluster bootstrap (1000, seed 42) by original image. Paired comparison Combined minus A on the same photos (FAR and FRR differences with bootstrap CI). Ambiguous photos: acceptance rate per method, reported alone.

## 6. Pre-registered decision rule (on stratum D only)
Integrating a VLM is justified only if ALL hold against the matching A-hard or A-strict:
- R1 at least 30 consensus-unsuitable photos in D (else UNDERPOWERED/EXPLORATORY, no adoption decision);
- R2 Combined FAR at least 10 percentage points below A's FAR, paired 95% CI excluding 0;
- R3 Combined FRR at most 10 points above A's FRR;
- R4 invalid-JSON <= 5% and median latency <= 15 s per image on the Kaggle GPU used;
- R5 the FAR gain is present in at least two of the three scalp sources (no single-source result).
Strata E and T, and overall accuracy, are never used in R1-R5. Failing any rule is a negative finding and is reported as such. A pass is a laboratory result on public photos, not proof for smartphone photos.

## 7. Choosing 2B or 4B (pilot of about 30 dev images; decided before any final run)
The pilot is far too small to rank models statistically; it only catches failures and large gaps. Therefore:
**Gates (each model must pass all):** G1 valid-JSON >= 95% (28 of 30); G2 median latency <= 15 s and p95 <= 30 s on Kaggle; G3 peak GPU memory <= 14 GB; G4 run errors <= 1 image; G5 no collapse: not the same answer for more than 90% of images; no NaN/empty outputs (guards the T4 half-precision risk).
**Comparison, in counts, never overall accuracy alone:** on pilot natural-unsuitable photos (false acceptances, count of N), on pilot suitable photos (false rejections, count of N), per failure category (counts table), failure-category agreement with the owner, on synthetic severe variants (reported separately).
**Rule:** choose the 2B model if it passes G1-G5 and is not worse than the 4B model by 3 or more additional false acceptances or 2 or more additional false rejections; otherwise choose the 4B model if it passes G1-G5; if neither passes, stop and revise the prompt on dev images (new prompt version). Ties go to the smaller model. Only the chosen model is run on final data; the other is never scored on final data. The prompt may change (new version) from pilot findings; sections 5-6 may not.

## 8. Reproducibility
Pin model repository, commit hash, prompt SHA-256, manifest SHA-256, Transformers/torch/Pillow versions, GPU, dtype, decoding settings; keep `pip freeze` and `nvidia-smi` output; seed 42 for sampling and bootstrap. Original Kaggle outputs are kept unedited.

## 9. Hard constraints
No retraining, no threshold/verdict/weights change, no frontend or production change, no Ollama/RAG/ChromaDB, no private photos, no photo sent to any hosted API, nothing large installed on the laptop. Only the `stimuli/` folder (public-dataset scalp photos, PRIVATE Kaggle dataset) leaves the laptop. `research/exp1/stimuli/` and `research/exp1/private/` are excluded from Git before any image is generated.
