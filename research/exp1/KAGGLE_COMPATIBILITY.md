# Kaggle / Qwen3-VL compatibility review (nothing downloaded or run)
| Item | What the official documentation says | Status / what the script does |
|---|---|---|
| Model classes | Transformers docs: `Qwen3VLForConditionalGeneration` and `AutoProcessor` | VERIFIED in docs; script uses them |
| Minimum Transformers version | NOT stated. The docs page is for v5.21.1 and says the model was added on 2025-09-15; the model cards say to use the latest release or build from source | UNVERIFIED which exact version works on Kaggle. Plan: `pip install -U transformers accelerate`, print the version, run the smoke test, then PIN that exact version for pilot and final |
| Loading API | Docs example: `from_pretrained(..., device_map="auto", attn_implementation="sdpa")`; the model card uses `dtype="auto"` | Script uses `dtype=` and falls back to `torch_dtype=` for older versions; `attn_implementation="sdpa"` |
| Image input | Docs chat example passes an image URL; the processor's `images` argument accepts PIL images, arrays or tensors | Script does NOT rely on a PIL object inside the chat message: it builds the prompt text with an image placeholder and calls `processor(text=[text], images=[PIL image])`. Not yet executed |
| Output decoding | Docs: `inputs.pop("token_type_ids", None)`; trim input tokens; `batch_decode(..., skip_special_tokens=True, clean_up_tokenization_spaces=False)` | Same pattern |
| Image size / token budget | Docs give patch size 16, spatial merge 2; no min/max-pixel guidance on that page | Script resizes each image to max side 768 px itself (about 576 visual tokens), so memory is predictable |
| dtype | Not specified by the docs. Weights are BF16 | Kaggle T4 has no native bfloat16 (my knowledge, unverified here): default float16; the smoke test and gate G5 check for garbage/NaN. Fallback: float32 is only plausible for the 2B model |
| GPU memory | No official figures. File sizes: 2B 4.26 GB, 4B 8.89 GB | Single-GPU placement (`device_map={"":0}`) by default; peak memory measured and gated (<=14 GB of 16 GB); out-of-memory errors are logged and the run continues |
| Structured JSON | Not mentioned on either model card | Prompt asks for one JSON object; the script validates every key and value; invalid = refusal and counted |
| Kaggle GPU | Reported (third-party): two T4 16 GB, P100 withdrawn, 12 h sessions | Check the accelerator list in YOUR notebook before the pilot |
| Internet on Kaggle | Needed once for the Hugging Face download | Notebook is private; only public-dataset stimuli are attached |
| Dependency pinning | - | After the smoke test: write the exact `transformers`, `accelerate`, `torch`, `Pillow` versions into `kaggle_code/requirements_kaggle_pins.txt` and install with `==`; export `pip freeze` with every run |
Known untested points (first real test is the smoke test, on approval): the processor call pattern, float16 numerical behaviour on T4, and whether `inp.to(model.device)` handles pixel dtype.

## Addendum 2026-11-23 - checked against the official Qwen3-VL GitHub README
- Minimum Transformers: README says Qwen3-VL "requires transformers >= 4.57.0". VERIFIED. Floor is set in `kaggle_code/requirements_kaggle_pins.txt`; the exact version is pinned after the smoke test.
- `qwen-vl-utils`: README pins `0.0.14`. NOT needed by my script (it uses the Hugging Face processor directly); do not install it.
- Image input: README shows `file:///` paths, URLs or base64 in the message (qwen-vl-utils route); the Transformers docs show the processor `images` argument accepting PIL. My script uses the processor route (PIL); UNTESTED until the smoke test.
- Resolution: README says sizes are rounded to multiples of 32 and budgets one image at 256-1280 visual tokens; with my 768 px cap a typical image is about 576 tokens (inside the budget). The README says to set min/max pixels "based on available GPU memory".
- Attention: README recommends FlashAttention 2 and says it works only in fp16/bf16. FlashAttention 2 needs newer GPUs than a T4 (my knowledge, unverified here), so the script uses `sdpa` as the Transformers docs show.
- dtype: README default is `dtype="auto"` (BF16 weights). A T4 does not natively support bfloat16 (stated in a Hugging Face forum reply). I found NO source that confirms or denies float16 problems for Qwen3-VL specifically; reports exist of fp16 instability for another multimodal model (Gemma 3) on T4. So float16 correctness is an open risk, tested by gate G5 and the smoke test. Smoke-test order: fp16 first, then `--dtype bfloat16` if outputs are empty/garbage.
- Memory: README gives no figure. Budget gate stays 14 GB of 16 GB.
- Pinning: `kaggle_code/requirements_kaggle_pins.txt` (floor now, exact versions after smoke test) + `pip freeze` exported with every run.
