"""Runs a repeatable test batch against your RUNNING server and writes the results to a table.

1. Start the server (run_server.bat) and leave it open.
2. In another terminal, from the project folder:
     C:\\Haircare\\hair_care_advisor\\venv\\Scripts\\python.exe scripts\\run_test_batch.py

What it tests (all automatic):
  A. Held-out FRONT photos   - random, balanced bald / not bald, only from the TEST split the model never trained on.
  B. Held-out CROWN photos   - from the TEST split of the scalp data.
  C. Quality stress          - the same few front photos made dark, bright, blurry and tiny.
  D. Wrong-type photos       - generated pictures (plain colour, noise, gradient) + any photos you drop in test_photos\\wrong.
  E. Consistency             - the same photos sent 3 times; the answer should not change.

Output (folder test_photos\\): copies of every photo used, results.csv, summary.md.
Photos are only sent to your own server on this computer.
"""
import argparse
import csv
import io
import json
import os
import random
import shutil
import urllib.request
import uuid
from collections import Counter

from PIL import Image, ImageFilter, ImageEnhance

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
a = argparse.ArgumentParser()
a.add_argument("--raw", default=r"C:\Haircare\kaggle_upload\raw", help="folder that contains balding\\, dryness_dandruff\\ ...")
a.add_argument("--server", default="http://127.0.0.1:8000")
a.add_argument("--n-front", type=int, default=20, help="total front photos (half bald, half not)")
a.add_argument("--n-crown", type=int, default=20)
a.add_argument("--out", default=os.path.join(ROOT, "test_photos"))
a.add_argument("--seed", type=int, default=42)
args = a.parse_args()
random.seed(args.seed)
for d in ("front", "crown", "quality", "wrong"):
    os.makedirs(os.path.join(args.out, d), exist_ok=True)


def read_rows(name):
    with open(os.path.join(ROOT, "data", name), newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r["split"] == "test"]


def post(slot, jpeg_bytes, fname):
    b = uuid.uuid4().hex
    body = b"".join([
        f"--{b}\r\nContent-Disposition: form-data; name=\"{slot}\"; filename=\"{fname}\"\r\nContent-Type: image/jpeg\r\n\r\n".encode(),
        jpeg_bytes, f"\r\n--{b}\r\nContent-Disposition: form-data; name=\"heatmap\"\r\n\r\nfalse\r\n--{b}--\r\n".encode()])
    req = urllib.request.Request(args.server + "/predict", data=body, headers={"Content-Type": "multipart/form-data; boundary=" + b})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return {"error": json.loads(e.read()).get("error", {}).get("code", str(e.code))}
        except Exception:
            return {"error": str(e.code)}


def to_jpeg(img):
    buf = io.BytesIO(); img.convert("RGB").save(buf, "JPEG", quality=92); return buf.getvalue()


def summarize(resp, slot):
    """-> (photo_status, flags, {condition: (verdict, prob)})"""
    if "error" in resp:
        return "error:" + str(resp["error"]), "", {}
    sr = [s for s in resp["slots"] if s["slot"] == slot]
    if not sr:
        return "no_slot", "", {}
    sr = sr[0]
    return sr["check"]["status"], "|".join(sr["check"]["flags"]), {c["condition"]: (c["verdict"], c.get("probability")) for c in sr["conditions"]}


rows_out = []


def record(group, slot, name, jpeg, expected, repeat=1):
    for k in range(repeat):
        resp = post(slot, jpeg, name)
        status, flags, conds = summarize(resp, slot)
        if not conds:
            rows_out.append(dict(group=group, file=name, run=k + 1, photo_status=status, flags=flags, condition="", expected="", verdict="", probability="", outcome="error" if status.startswith("error") else "no_answer"))
        for cond, (v, p) in conds.items():
            exp = expected.get(cond) if expected else None
            if exp is None:
                outcome = ""
            elif v == "possible":
                outcome = "correct" if exp == 1 else "wrong"
            elif v == "none_seen":
                outcome = "correct" if exp == 0 else "wrong"
            elif v == "unsure":
                outcome = "unsure"
            else:
                outcome = "refused"
            rows_out.append(dict(group=group, file=name, run=k + 1, photo_status=status, flags=flags, condition=cond,
                                 expected="" if exp is None else exp, verdict=v, probability="" if p is None else round(p, 3), outcome=outcome))


# server alive?
try:
    health = json.loads(urllib.request.urlopen(args.server + "/health", timeout=10).read())
    print("Server OK, version", health.get("app_version"), "status", health.get("status"))
except Exception as e:
    raise SystemExit(f"Cannot reach the server at {args.server}. Start run_server.bat first.\n{e}")

# A. front
fr = read_rows("balding_labels.csv")
pos = [r for r in fr if r["balding"] == "1"]; neg = [r for r in fr if r["balding"] == "0"]
pick = random.sample(pos, min(args.n_front // 2, len(pos))) + random.sample(neg, min(args.n_front // 2, len(neg)))
front_imgs = []
for i, r in enumerate(pick):
    src = os.path.join(args.raw, *r["filepath"].split("/"))
    if not os.path.exists(src):
        print("missing", src); continue
    name = f"front_{i:02d}_{'bald' if r['balding']=='1' else 'notbald'}.jpg"
    shutil.copy(src, os.path.join(args.out, "front", name))
    jb = open(src, "rb").read()
    front_imgs.append((name, src, int(r["balding"])))
    record("A_front_heldout", "front", name, jb, {"balding": int(r["balding"])})
print("A done:", len(front_imgs), "front photos")

# B. crown
cr = read_rows("scalp_labels.csv")
pick = random.sample(cr, min(args.n_crown, len(cr)))
for i, r in enumerate(pick):
    src = os.path.join(args.raw, *r["filepath"].split("/"))
    if not os.path.exists(src):
        print("missing", src); continue
    tags = "_".join(c for c in ("dryness", "dandruff", "low_density") if r[c] == "1") or "healthy"
    name = f"crown_{i:02d}_{tags}.jpg"
    shutil.copy(src, os.path.join(args.out, "crown", name))
    record("B_crown_heldout", "crown", name, open(src, "rb").read(), {c: int(r[c]) for c in ("dryness", "dandruff", "low_density") if r[c] != ""})
print("B done:", len(pick), "crown photos")

# C. quality stress on 4 front photos (2 bald, 2 not)
base = [x for x in front_imgs if x[2] == 1][:2] + [x for x in front_imgs if x[2] == 0][:2]
for name, src, lab in base:
    im = Image.open(src).convert("RGB")
    variants = {"dark": ImageEnhance.Brightness(im).enhance(0.25), "bright": ImageEnhance.Brightness(im).enhance(2.6),
                "blurry": im.filter(ImageFilter.GaussianBlur(10)), "tiny": im.resize((72, 72))}
    for vn, vi in variants.items():
        n2 = name.replace(".jpg", f"__{vn}.jpg")
        vi.save(os.path.join(args.out, "quality", n2), quality=92)
        record("C_quality_stress", "front", n2, to_jpeg(vi), {"balding": lab})
print("C done")

# D. wrong type
gen = {}
W_, H_ = 640, 480
gen["plain_green.jpg"] = Image.new("RGB", (W_, H_), (80, 140, 90))
gen["noise.jpg"] = Image.frombytes("RGB", (W_, H_), os.urandom(W_ * H_ * 3))
g = Image.new("RGB", (W_, H_)); g.putdata([(int(255 * x / W_), int(255 * y / H_), 128) for y in range(H_) for x in range(W_)]); gen["gradient.jpg"] = g
gen["white.jpg"] = Image.new("RGB", (W_, H_), (250, 250, 250))
wrong_dir = os.path.join(args.out, "wrong")
for n, im in gen.items():
    im.save(os.path.join(wrong_dir, "generated_" + n), quality=92)
mine = [f for f in sorted(os.listdir(wrong_dir)) if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]
for f in mine:
    im = Image.open(os.path.join(wrong_dir, f)).convert("RGB"); im.thumbnail((1024, 1024))
    record("D_wrong_type", "front", f, to_jpeg(im), None)
    record("D_wrong_type", "crown", "crown__" + f, to_jpeg(im), None)
print("D done:", len(mine), "wrong-type photos (put your own room/object photos in", wrong_dir, "and run again)")

# E. consistency: 5 photos x 3 sends
for name, src, lab in front_imgs[:3] + front_imgs[-2:]:
    record("E_consistency", "front", name, open(src, "rb").read(), {"balding": lab}, repeat=3)
print("E done")

# write
cols = ["group", "file", "run", "photo_status", "flags", "condition", "expected", "verdict", "probability", "outcome"]
with open(os.path.join(args.out, "results.csv"), "w", newline="", encoding="utf-8") as f:
    wr = csv.DictWriter(f, fieldnames=cols); wr.writeheader(); wr.writerows(rows_out)

L = ["# Test batch summary", "", f"Server version: {health.get('app_version')}  |  seed {args.seed}", ""]
for grp, title in [("A_front_heldout", "A. Held-out front photos"), ("B_crown_heldout", "B. Held-out crown photos")]:
    L += [f"## {title}", "", "| Condition | Photos | Correct | Wrong | Unsure | Refused |", "|---|---|---|---|---|---|"]
    for cond in sorted({r["condition"] for r in rows_out if r["group"] == grp and r["condition"]}):
        rs = [r for r in rows_out if r["group"] == grp and r["condition"] == cond]
        c = Counter(r["outcome"] for r in rs)
        L.append(f"| {cond} | {len(rs)} | {c['correct']} | {c['wrong']} | {c['unsure']} | {c['refused']} |")
    pos_rs = [r for r in rows_out if r["group"] == grp and r["expected"] == 1]
    neg_rs = [r for r in rows_out if r["group"] == grp and r["expected"] == 0]
    L += ["", f"Of photos that DO show the condition: {sum(r['outcome']=='correct' for r in pos_rs)}/{len(pos_rs)} flagged 'possible'.",
          f"Of photos that do NOT: {sum(r['outcome']=='correct' for r in neg_rs)}/{len(neg_rs)} answered 'none seen'.", ""]
L += ["## C. Quality stress (dark / bright / blurry / tiny versions)", "", "| Variant | Photos | Verdicts |", "|---|---|---|"]
for vn in ("dark", "bright", "blurry", "tiny"):
    rs = [r for r in rows_out if r["group"] == "C_quality_stress" and f"__{vn}" in r["file"]]
    L.append(f"| {vn} | {len(rs)} | {dict(Counter(r['verdict'] for r in rs))} |")
L += ["", "Good behaviour here = 'unsure' or 'refused' or a quality warning, not a confident answer.", "",
      "## D. Wrong-type photos", "", "| Slot file | Photo status | Verdicts |", "|---|---|---|"]
for f in sorted({r["file"] for r in rows_out if r["group"] == "D_wrong_type"}):
    rs = [r for r in rows_out if r["group"] == "D_wrong_type" and r["file"] == f]
    L.append(f"| {f} | {rs[0]['photo_status']} | {dict(Counter(r['verdict'] for r in rs))} |")
L += ["", "Good behaviour here = photo status 'mismatch' and verdict 'unsuitable' (refused).", "", "## E. Consistency (3 sends each)", "", "| Photo | Condition | Verdicts across 3 sends | Same? |", "|---|---|---|---|"]
for f in sorted({r["file"] for r in rows_out if r["group"] == "E_consistency"}):
    rs = [r for r in rows_out if r["group"] == "E_consistency" and r["file"] == f]
    vs = [r["verdict"] for r in rs]
    L.append(f"| {f} | {rs[0]['condition']} | {vs} | {'yes' if len(set(vs)) == 1 else 'NO'} |")
open(os.path.join(args.out, "summary.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
print("\n".join(L))
print("\nSaved:", os.path.join(args.out, "results.csv"), "and summary.md")
