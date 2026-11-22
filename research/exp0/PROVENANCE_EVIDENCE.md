# Scalp dataset provenance: evidence from project files (2026-11-23)
Method: read the README files shipped inside each Roboflow export, `data/README.md`, `docs/dataset_audit.md`, the Kaggle training summaries and file timestamps. The Roboflow and Kaggle web pages could NOT be fetched, so nothing below was checked against the live sites.
## Evidence table
| Source (images used) | README says | Export date | Evidence about who owns/uploaded it |
|---|---|---|---|
| `dryness_dandruff` = Roboflow `hairdata` (186 images; 180 used) | owner `aungkaung-phyo`, project `hairdata-nyeix-wkpgb`, "Provided by a Roboflow user", CC BY 4.0 | 2026-09-20 | File names contain `istockphoto-<id>` (stock-agency IDs). `data/README.md` credits `getready/hairdata-nyeix`: the same name with a random suffix `-wkpgb` removed. |
| `extra_scalp/dandruff_big_chunks` (370; 353 used) | owner `scalpdet`, CC BY 4.0 | 2026-08-12 | Third-party handle. Export applied resize 512x512 and x3 brightness augmentation, so these are derived copies. Original capture source unknown. |
| `healthy_scalp` (515; 350 used) | owner `defaultworkspace-c3ew1`, project dated 2025-09-07, CC BY 4.0 | 2025-10-09 | Third-party handle (a default workspace name). Images are 1280x720 screen captures of people in a public venue; consent unknown. |
| Kaggle bald classification (balding model) | not stored in the files; `dataset_audit.md` says "check before publishing" | n/a | Third party (Ashish Jangra). Face photos. |
## What the evidence does and does not show
1. **Ownership of `hairdata` is UNDETERMINED.** The handle `aungkaung-phyo` is very close to the Kaggle username `aungkaungphyo` (training summaries show the Kaggle dataset `aungkaungphyo/hair-images-zip` was used). That is suggestive, not proof. A Roboflow project name ending in a random suffix (`-wkpgb`) is the pattern one would expect for a copy/fork of an existing project `hairdata-nyeix`; the project's own earlier credit in `data/README.md` points to `getready`. This is an inference: it would mean the account `aungkaung-phyo` copied someone else's project, and that the original uploader is `getready`. Only logging in to Roboflow can show whether the project is in your workspace and whether it is a fork.
2. **Even if you own the Roboflow project, that does not settle the images.** The `istockphoto-` file names suggest commercial stock photos. A CC BY 4.0 label placed by someone who does not hold the copyright does not grant rights to others.
3. **No source has a verified redistribution right.** Every CC BY 4.0 statement is a README line from a Roboflow export, not checked on the live page, and none documents where the original photos came from. `healthy_scalp` additionally has a privacy question.
4. **The existing Kaggle dataset `hair-images-zip` was created 2026-10-13 from `raw.zip` (about 174 MB, same size as the local zip)** and so likely contains all three scalp sources and the balding photos. Its visibility is unchecked.
5. **Research use vs redistribution:** local use on the owner's PC for this project is a different act from copying the images to Kaggle or publishing them. This audit supports neither claim; it only records what is unknown.
## Rule adopted for Experiment 1 (pending owner approval)
- Images from the four sources above are treated as `uncertain licence`.
- They may be used locally for the study (the professor requires public datasets) but are NOT included in any new Kaggle upload.
- Only images with a verified per-file licence and author (see `exp1/FEASIBILITY_AND_SUPPLEMENT.md`, option C) may be uploaded.
## To resolve (owner actions)
1. Log in to Roboflow: is `hairdata-nyeix-wkpgb` in your workspace? Is it a fork of `getready/hairdata-nyeix`? (Settings shows this.)
2. Check Kaggle `hair-images-zip` visibility (Private/Public) and its Data tab.
3. Open each Roboflow project page and copy its licence and "original source" text into this file.
