"""Experiment 1 - VLM photo-suitability run. RUNS ON KAGGLE GPU ONLY (never on the laptop). Research code, not part of the app.
Reads ONLY: stimuli/manifest_public.csv (stim_id, set, file), the images, and the prompt file. It never sees labels, sources, gate or classifier output.
Usage in a notebook cell:
  !python kaggle_vlm_run.py --stimuli /kaggle/input/<stimuli-dataset> --prompt /kaggle/input/<code-dataset>/suitability_v1.txt --set dev --ids pilot_ids.txt --out /kaggle/working/exp1_out
  --set final_natural / final_synth are refused unless --frozen-protocol-sha256 matches --expect-sha256 (you type both after the protocol is approved)."""
import argparse, csv, hashlib, json, os, platform, re, sys, time, traceback
p = argparse.ArgumentParser()
p.add_argument("--stimuli", required=True); p.add_argument("--prompt", required=True); p.add_argument("--set", required=True, choices=["dev", "final_natural", "final_synth", "smoke"])
p.add_argument("--ids", default=None, help="optional text file with one stim_id per line (pilot list)"); p.add_argument("--limit", type=int, default=None)
p.add_argument("--model", default="Qwen/Qwen3-VL-4B-Instruct"); p.add_argument("--revision", default=None, help="pin a Hugging Face commit hash for reproducibility")
p.add_argument("--dtype", default="float16", choices=["float16", "bfloat16", "float32"]); p.add_argument("--device-map", default="single", choices=["single", "auto"], help="single = whole model on GPU 0 (default); auto = let Transformers split across GPUs"); p.add_argument("--max-side", type=int, default=768); p.add_argument("--max-new-tokens", type=int, default=60)
p.add_argument("--out", required=True); p.add_argument("--frozen-protocol-sha256", default=None); p.add_argument("--expect-sha256", default=None)
a = p.parse_args()
if a.set.startswith("final") and (not a.frozen_protocol_sha256 or a.frozen_protocol_sha256 != a.expect_sha256):
    sys.exit("REFUSED: final sets need the frozen protocol hash (--frozen-protocol-sha256 and --expect-sha256 must match). Do not run final sets before approval.")
import torch
from PIL import Image
import transformers
from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
os.makedirs(a.out, exist_ok=True)
prompt = open(a.prompt, encoding="utf-8").read(); prompt_sha = hashlib.sha256(prompt.encode()).hexdigest()
manifest = list(csv.DictReader(open(os.path.join(a.stimuli, "manifest_public.csv"), newline="")))
sel = [r for r in manifest if (r["set"] == a.set if a.set != "smoke" else r["set"] == "dev")]
if a.ids: keep = {l.strip() for l in open(a.ids) if l.strip()}; sel = [r for r in sel if r["stim_id"] in keep]
if a.set == "smoke": sel = sel[:3]
if a.limit: sel = sel[:a.limit]
dt = {"float16": torch.float16, "bfloat16": torch.bfloat16, "float32": torch.float32}[a.dtype]
t0 = time.time(); proc = AutoProcessor.from_pretrained(a.model, revision=a.revision)
dmap = {"": 0} if (a.device_map == "single" and torch.cuda.is_available()) else "auto"
kw = dict(revision=a.revision, device_map=dmap, attn_implementation="sdpa")
try: model = Qwen3VLForConditionalGeneration.from_pretrained(a.model, dtype=dt, **kw).eval()          # newer Transformers: `dtype`
except TypeError: model = Qwen3VLForConditionalGeneration.from_pretrained(a.model, torch_dtype=dt, **kw).eval()  # older Transformers: `torch_dtype`
load_s = time.time() - t0
VALID = {"suitable": {"yes", "no", "unsure"}, "retake": {"yes", "no"}, "failure_category": {"none", "wrong_view", "scalp_not_visible_or_too_small", "blurry", "too_dark_or_bright", "obstructed", "not_a_photo_or_multiple"}}
def parse(txt):
    m = re.search(r"\{.*\}", txt, re.S)
    if not m: return None
    try: j = json.loads(m.group(0))
    except Exception: return None
    return j if isinstance(j, dict) and all(k in j and j[k] in VALID[k] for k in VALID) else None
rows, errs = [], []
if torch.cuda.is_available(): torch.cuda.reset_peak_memory_stats()
for r in sel:
    try:
        im = Image.open(os.path.join(a.stimuli, r["file"])).convert("RGB"); im.thumbnail((a.max_side, a.max_side))
        msgs = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt}]}]
        text = proc.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)       # prompt text with an image placeholder
        inp = proc(text=[text], images=[im], return_tensors="pt").to(model.device)               # image goes in as a PIL object
        inp.pop("token_type_ids", None)                                                           # as in the official example
        t = time.time()
        with torch.no_grad(): g = model.generate(**inp, max_new_tokens=a.max_new_tokens, do_sample=False)
        if torch.cuda.is_available(): torch.cuda.synchronize()
        lat = time.time() - t; txt = proc.batch_decode(g[:, inp["input_ids"].shape[1]:], skip_special_tokens=True, clean_up_tokenization_spaces=False)[0]; j = parse(txt)
        rows.append({"stim_id": r["stim_id"], "set": r["set"], "valid_json": int(j is not None), "suitable": (j or {}).get("suitable", ""), "failure_category": (j or {}).get("failure_category", ""),
                     "retake": (j or {}).get("retake", ""), "latency_s": round(lat, 3), "raw_text": txt.replace("\n", " ")[:300]})
    except Exception as e:
        if torch.cuda.is_available(): torch.cuda.empty_cache()   # after an out-of-memory error, free memory and carry on with the next image
        errs.append({"stim_id": r["stim_id"], "error": repr(e), "trace": traceback.format_exc()[-500:]})
        rows.append({"stim_id": r["stim_id"], "set": r["set"], "valid_json": 0, "suitable": "", "failure_category": "", "retake": "", "latency_s": "", "raw_text": "ERROR"})
tag = a.set
with open(os.path.join(a.out, f"vlm_predictions_{tag}.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["stim_id"]); w.writeheader(); w.writerows(rows)
json.dump(errs, open(os.path.join(a.out, f"errors_{tag}.json"), "w"), indent=1)
meta = {"model": a.model, "revision_requested": a.revision, "resolved_commit": getattr(getattr(model, "config", None), "_commit_hash", None), "dtype": a.dtype, "device_map": a.device_map, "attn_implementation": "sdpa", "image_format": "PIL RGB, thumbnail to max side via --max-side", "processor_call": "apply_chat_template(tokenize=False) + processor(text, images)", "decoding": "greedy, do_sample=False", "max_new_tokens": a.max_new_tokens,
        "image_max_side": a.max_side, "prompt_file": os.path.basename(a.prompt), "prompt_sha256": prompt_sha, "set": a.set, "n_images": len(sel), "n_errors": len(errs), "model_load_seconds": round(load_s, 1),
        "peak_gpu_mem_gb": round(torch.cuda.max_memory_allocated() / 2**30, 2) if torch.cuda.is_available() else None, "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "torch": torch.__version__, "transformers": transformers.__version__, "python": platform.python_version(), "manifest_sha256": hashlib.sha256(open(os.path.join(a.stimuli, "manifest_public.csv"), "rb").read()).hexdigest(),
        "protocol_sha256": a.frozen_protocol_sha256}
json.dump(meta, open(os.path.join(a.out, f"run_metadata_{tag}.json"), "w"), indent=1); print(json.dumps(meta, indent=1))
