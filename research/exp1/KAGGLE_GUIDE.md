# Experiment 1 - beginner Kaggle guide
Nothing here has been run. Do not start until the owner has approved the protocol, the model and the first upload. Laptop commands are for **Command Prompt**. First run these two lines once per window (real paths checked on your PC):
```
cd /d C:\Haircare\v4\hair_care_advisor
set PY=C:\Haircare\hair_care_advisor\venv\Scripts\python.exe
set RAW=C:\Haircare\kaggle_upload\raw
```
Then use `"%PY%"` for Python and `%RAW%` for the photo folder.

## Part 1 - Prepare the images (laptop)
0. **Git safety first:** run `git check-ignore -v research/exp1/stimuli/x.jpg research/exp1/private/x.csv`. Both lines must print a rule from `.gitignore`. If either prints nothing, STOP and tell me.
1. Check the split: `"%PY%" research\exp0\verify_split.py %RAW%` (all lines must say PASS). Then `"%PY%" research\exp1\verify_disjoint.py --simulate` (all PASS; needs no images).
2. Build the natural sets: `"%PY%" research\exp1\build_stimuli.py --raw %RAW%`. It makes `research\exp1\stimuli\` (images with random names, `manifest_public.csv`, `CHECKSUMS.sha256`) and `research\exp1\private\` (the secret lists and blank rating sheets). Counts printed: final_natural 174, dev natural 36, dev synthetic 16. Then run `"%PY%" research\exp1\verify_disjoint.py` (all PASS) and `git status --short` (nothing under `research\exp1\stimuli` or `private` may appear).
3. Rate. You fill `private\rating_dev_rater1.csv` (36 photos, rate these FIRST: they tell us whether enough unsuitable photos exist) and `private\rating_final_rater1.csv` (174 photos). The second person fills `private\rating_final_rater2.csv` on their own, in their own copy. Follow `LABELING_GUIDE.md`. Open images from `stimuli\<set>\<stim_id>.jpg` (the `image_file` column).
4. Disagreements: sit together once; write the agreed answers in `private\adjudication.csv` with columns `stim_id,label,failure_category`. Unlisted disagreements stay `ambiguous`.
5. Build the synthetic final set (only after step 4): `"%PY%" research\exp1\build_stimuli.py --raw %RAW% --phase synthetic` and `"%PY%" research\exp1\verify_disjoint.py` again. One person then rates the file `private\spot_check_rater1.csv` (about 20% of severe variants) to confirm they really look unsuitable; report the result.
6. Make the pilot list: `"%PY%" research\exp1\score_suitability.py --make-pilot`. It writes `private\pilot_ids.txt` (only image IDs, no labels). It prints how many ambiguous dev photos exist; the pilot should contain at least 3. If not, ask me to extend the dev set.
7. Run the existing checks on all stimuli: `"%PY%" research\exp1\baseline_run.py` (CPU, a few minutes). It writes `research\exp1\results\baseline_predictions.csv`. Nothing about the app changes.
8. Freeze the protocol (after approval): copy `PROTOCOL_DRAFT.md` to `PROTOCOL.md`, then `certutil -hashfile research\exp1\PROTOCOL.md SHA256`. Write the hash in your notes.
**Leakage safeguards:** the test photos are exactly the frozen lists (`research\exp0\frozen_lists\`); dev photos come only from train rows; `build_stimuli.py` never reads the app's predictions; the script that talks to the VLM never reads `private\`.
**Counts and checksums:** `research\exp1\stimuli\CHECKSUMS.sha256` lists every image. After uploading to Kaggle you verify the same list there (Part 2).

## Part 2 - Kaggle setup
Do this in the Kaggle website, logged in. Kaggle may ask you to verify your phone number before offering GPU and Internet.
1. **Upload two PRIVATE datasets** (Datasets, New Dataset, set visibility Private):
   - `hsa-exp1-stimuli`: the whole folder `research\exp1\stimuli\` (it contains ATTRIBUTION.txt). Visibility **Private**. Read `DATA_LICENCE_PRIVACY_REVIEW.md` first; no face photos are included.
   - `hsa-exp1-code`: these files only: `research\exp1\kaggle_code\kaggle_vlm_run.py`, `suitability_v1.txt`, `verify_checksums.py`, and `research\exp1\private\pilot_ids.txt`. Never upload anything else from `private\`.
2. **New Notebook** (Code, New Notebook). Right sidebar: **Add Input** and attach both datasets.
3. **Settings** in the sidebar: Accelerator = GPU (pick what Kaggle offers; reports say T4 x2, and that the older P100 option was withdrawn in 2026, so check what your account shows). Internet = ON (needed once to download the model from Hugging Face).
4. Run these cells one at a time (put each block in its own cell). After the smoke test passes, copy the printed `transformers`, `accelerate`, `torch`, `Pillow` versions into `kaggle_code\requirements_kaggle_pins.txt` and install exactly those (`pip install transformers==X.Y.Z`) for the pilot and the final run; see `KAGGLE_COMPATIBILITY.md`.
```
!nvidia-smi
```
```
!pip install -q -U transformers accelerate
import transformers, torch; print(transformers.__version__, torch.__version__, torch.cuda.is_available())
```
```
import os; os.environ["HF_HOME"] = "/kaggle/temp/hf"
!python /kaggle/input/hsa-exp1-code/verify_checksums.py /kaggle/input/hsa-exp1-stimuli /kaggle/input/hsa-exp1-stimuli/CHECKSUMS.sha256
```
The last cell must end with `0 problems`.
5. **Smoke test** (3 dev images, tiny): 
```
!python /kaggle/input/hsa-exp1-code/kaggle_vlm_run.py --stimuli /kaggle/input/hsa-exp1-stimuli --prompt /kaggle/input/hsa-exp1-code/suitability_v1.txt --set smoke --model Qwen/Qwen3-VL-2B-Instruct --out /kaggle/working/exp1_out
```
It downloads the model (about 4.3 GB for the 2B model) into temporary storage, runs 3 images and prints a metadata block (GPU, peak memory, versions). Check that `vlm_predictions_smoke.csv` has JSON in the `suitable` columns. If answers are empty or nonsense, the likely cause is half-precision on a T4 (no native bfloat16); try `--dtype float32` for the 2B model, and report back. Nothing is assumed to work until this passes.

## Part 3 - Pilot (development images only, about 30)
1. Run the pilot with the smaller model first, then the larger:
```
!python /kaggle/input/hsa-exp1-code/kaggle_vlm_run.py --stimuli /kaggle/input/hsa-exp1-stimuli --prompt /kaggle/input/hsa-exp1-code/suitability_v1.txt --set dev --ids /kaggle/input/hsa-exp1-code/pilot_ids.txt --model Qwen/Qwen3-VL-2B-Instruct --out /kaggle/working/pilot_2b
```
Repeat with `--model Qwen/Qwen3-VL-4B-Instruct --out /kaggle/working/pilot_4b` (about 8.9 GB download).
2. Download both `vlm_predictions_dev.csv` and `run_metadata_dev.json` (Output panel), then on the laptop: `"%PY%" research\exp1\score_suitability.py --score-pilot <path>\vlm_predictions_dev.csv`. It reports accept/reject accuracy, category match, JSON validity, median latency. The metadata gives peak GPU memory. Apply the model-choice rule in protocol section 7 (gates G1-G5 plus counts of false acceptances, false rejections and failure categories, not overall accuracy). You may improve the prompt (name it `suitability_v2.txt`), but only using dev images.

## Part 4 - Final evaluation (only after approval and a frozen protocol)
Add the frozen hash to the commands (it makes the script refuse to run without it):
```
!python /kaggle/input/hsa-exp1-code/kaggle_vlm_run.py --stimuli /kaggle/input/hsa-exp1-stimuli --prompt /kaggle/input/hsa-exp1-code/suitability_v1.txt --set final_natural --model <CHOSEN MODEL> --revision <COMMIT HASH FROM THE PILOT METADATA> --frozen-protocol-sha256 <HASH> --expect-sha256 <HASH> --out /kaggle/working/exp1_out
```
Run it once more with `--set final_synth`. One run each. No prompt changes afterwards.

## Part 5 - Export from Kaggle
Run in a final cell, then download the whole `exp1_out` folder (Output tab, or Save Version > Save & Run All and download from the version's Output):
```
!pip freeze > /kaggle/working/exp1_out/pip_freeze.txt
!nvidia-smi > /kaggle/working/exp1_out/nvidia_smi.txt
!cp /kaggle/input/hsa-exp1-code/suitability_v1.txt /kaggle/working/exp1_out/
!cd /kaggle/working/exp1_out && sha256sum * > OUT_SHA256.txt
```
You get: per-image prediction CSVs, run metadata (model, commit, dtype, GPU, peak memory, versions, prompt hash, manifest hash), error logs, pip list, configuration. Do NOT export the images again. The ground-truth labels never go to Kaggle.

## Part 6 - Import and score on the laptop (no VLM needed)
1. Copy the downloaded folder to `research\exp1\results\kaggle_run_<date>\`.
2. Verify: `"%PY%" research\exp1\kaggle_code\verify_checksums.py research\exp1\results\kaggle_run_<date> research\exp1\results\kaggle_run_<date>\OUT_SHA256.txt` (the checksum file itself is excluded; ignore a mismatch for it only).
3. Score: `"%PY%" research\exp1\score_suitability.py --vlm research\exp1\results\kaggle_run_<date>\vlm_predictions_final_natural.csv --vlm-synth research\exp1\results\kaggle_run_<date>\vlm_predictions_final_synth.csv`
4. Outputs in `research\exp1\results\`: `metrics.json`, `table_natural_by_subset.csv`, `per_image_joined.csv`, `fig_far_frr.png` (figure needs matplotlib).
5. Archive: zip `research\exp1\` without `stimuli\` images, with `private\` kept offline, plus the frozen `PROTOCOL.md`, `CHECKSUMS.sha256` and the Kaggle outputs. Add the zip's SHA-256 to your notes.

## Time and quota (estimates)
Kaggle publishes a weekly GPU allowance of roughly 30 hours; the pilot should take well under an hour including downloads and the final run an hour or less. Verify your own quota in the notebook sidebar.
