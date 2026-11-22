"""Runs front + top-of-head PAIRS (one person each) through your running server, one request per person.

Put photos in  test_photos\\pairs\\  named like:
    person01_front.jpg   person01_crown.jpg
    person02_front.jpg   person02_crown.jpg   ...   (.jpg .jpeg .png .webp)
A person with only one of the two photos also works.

Run (server must be running):
    & "C:\\Haircare\\hair_care_advisor\\venv\\Scripts\\python.exe" scripts\\run_pairs.py
Output: test_photos\\pairs\\pairs_results.csv and pairs_summary.md
Only use photos of people who agreed to it. Photos are sent only to your own server on this computer.
"""
import csv, io, json, os, re, urllib.request, uuid
from PIL import Image, ImageOps

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
D = os.path.join(ROOT, "test_photos", "pairs")
SERVER = "http://127.0.0.1:8000"
os.makedirs(D, exist_ok=True)
people = {}
for f in sorted(os.listdir(D)):
    m = re.match(r"(.+)_(front|crown)\.(jpg|jpeg|png|webp)$", f, re.I)
    if m:
        people.setdefault(m.group(1), {})[m.group(2).lower()] = f
if not people:
    raise SystemExit(f"No photos found. Put files like person01_front.jpg and person01_crown.jpg in:\n{D}")


def jpeg(path):
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB"); im.thumbnail((1600, 1600))
    b = io.BytesIO(); im.save(b, "JPEG", quality=92); return b.getvalue()


def post(files):
    bd = uuid.uuid4().hex
    parts = []
    for slot, (name, data) in files.items():
        parts.append(f'--{bd}\r\nContent-Disposition: form-data; name="{slot}"; filename="{name}"\r\nContent-Type: image/jpeg\r\n\r\n'.encode() + data + b"\r\n")
    parts.append(f'--{bd}\r\nContent-Disposition: form-data; name="heatmap"\r\n\r\nfalse\r\n--{bd}--\r\n'.encode())
    req = urllib.request.Request(SERVER + "/predict", data=b"".join(parts), headers={"Content-Type": "multipart/form-data; boundary=" + bd})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=180).read())
    except urllib.error.HTTPError as e:
        return {"error": e.read().decode()[:200]}


rows = []
for p, fs in people.items():
    resp = post({s: (fs[s], jpeg(os.path.join(D, fs[s]))) for s in fs})
    if "error" in resp:
        rows.append(dict(person=p, slot="", photo_status="error", flags="", condition="", verdict=resp["error"], probability="")); continue
    for sr in resp["slots"]:
        for c in sr["conditions"]:
            rows.append(dict(person=p, slot=sr["slot"], photo_status=sr["check"]["status"], flags="|".join(sr["check"]["flags"]),
                             condition=c["condition"], verdict=c["verdict"], probability="" if c.get("probability") is None else round(c["probability"], 3)))
    print("done", p)
cols = ["person", "slot", "photo_status", "flags", "condition", "verdict", "probability"]
with open(os.path.join(D, "pairs_results.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
L = ["# Pair results (front + top-of-head per person)", "", "| Person | Front photo | Hairline | Crown photo | Dryness | Dandruff | Low density |", "|---|---|---|---|---|---|---|"]
for p in people:
    r = [x for x in rows if x["person"] == p]
    g = lambda c: next((f"{x['verdict']}" + (f" ({x['probability']})" if x["probability"] != "" else "") for x in r if x["condition"] == c), "-")
    st = lambda s: next((x["photo_status"] for x in r if x["slot"] == s), "-")
    L.append(f"| {p} | {st('front')} | {g('balding')} | {st('crown')} | {g('dryness')} | {g('dandruff')} | {g('low_density')} |")
open(os.path.join(D, "pairs_summary.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
print("\n".join(L)); print("\nSaved in", D)
