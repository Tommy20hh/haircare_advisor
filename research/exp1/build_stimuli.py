"""Experiment 1 - builds the image sets, blinded IDs, rating sheets and checksums. Runs on the laptop CPU (needs Pillow, pandas).
Phase 1 (natural + dev):   python research\\exp1\\build_stimuli.py --raw <RAW_ROOT>
Phase 2 (synthetic final, AFTER both raters finished):   python research\\exp1\\build_stimuli.py --raw <RAW_ROOT> --phase synthetic
Writes:  research\\exp1\\stimuli\\   (images + manifest_public.csv + CHECKSUMS.sha256)   <- the ONLY thing uploaded to Kaggle (private dataset)
         research\\exp1\\private\\   (source/labels/ratings; never upload, never commit)
Read-only on data\\ and the raw photos. Seed 42."""
import argparse, csv, hashlib, os, random, sys
import pandas as pd
from PIL import Image, ImageEnhance, ImageFilter
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
E1 = os.path.join(ROOT, "research", "exp1"); STIM = os.path.join(E1, "stimuli"); PRIV = os.path.join(E1, "private")
MAXSIDE = 1024  # same as the app's MAX_UPLOAD_SIDE
SYN = {"blur": (0.006, 0.02), "dark": (0.45, 0.15), "bright": (1.6, 2.6), "obstruct": (0.35, 0.60), "wide": (0.6, 0.3)}  # (moderate, severe)
SYN_EXPECT = {"blur": "blurry", "dark": "too_dark_or_bright", "bright": "too_dark_or_bright", "obstruct": "obstructed", "wide": "scalp_not_visible_or_too_small"}

def sid(*parts): return "s" + hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:8]
def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()
def load(raw, fp):
    im = Image.open(os.path.join(raw, fp)).convert("RGB"); im.thumbnail((MAXSIDE, MAXSIDE)); return im
def save(im, setname, stim):
    d = os.path.join(STIM, setname); os.makedirs(d, exist_ok=True); p = os.path.join(d, stim + ".jpg"); im.save(p, "JPEG", quality=90); return f"{setname}/{stim}.jpg"
def degrade(im, kind, sev, rng):
    v = SYN[kind][sev]; w, h = im.size
    if kind == "blur": return im.filter(ImageFilter.GaussianBlur(radius=max(w, h) * v))
    if kind in ("dark", "bright"): return ImageEnhance.Brightness(im).enhance(v)
    if kind == "obstruct":
        bw, bh = int(w * (v ** 0.5)), int(h * (v ** 0.5)); x, y = rng.randint(0, w - bw), rng.randint(0, h - bh)
        o = im.copy(); o.paste((120, 120, 120), (x, y, x + bw, y + bh)); return o
    if kind == "wide":
        c = Image.new("RGB", (w, h), (127, 127, 127)); s = im.resize((max(1, int(w * v)), max(1, int(h * v)))); c.paste(s, ((w - s.width) // 2, (h - s.height) // 2)); return c
def rows_to_csv(path, rows, cols):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); [w.writerow({c: r.get(c, "") for c in cols}) for r in rows]
PCOLS = ["stim_id", "set", "file"]
VCOLS = ["stim_id", "set", "file", "kind", "source", "orig_split", "filepath", "group", "original_id", "variant_type", "severity", "expected_label", "expected_category"]
ATTR = """Images in this folder are resized, re-encoded copies (renamed to random IDs) of public-dataset photos, kept PRIVATE for non-commercial university research only.
Sources (licence as stated in each dataset's own README; the licence of the underlying stock photos was not verified):
- roboflow_hairdata: https://universe.roboflow.com/aungkaung-phyo/hairdata-nyeix-wkpgb  (CC BY 4.0, provided by a Roboflow user)
- extra_dandruff_big_chunks: https://universe.roboflow.com/scalpdet/dandruff-big-chunks  (CC BY 4.0, provided by a Roboflow user)
- healthy_scalp: Roboflow defaultworkspace-c3ew1/healthy-scalp-p2ire (CC BY 4.0 per project docs)
Do not publish, share or make this dataset public.
"""
def write_checksums():
    open(os.path.join(STIM, "ATTRIBUTION.txt"), "w", encoding="utf-8").write(ATTR)
    lines = []
    for dp, _, fs in os.walk(STIM):
        for f in sorted(fs):
            if f != "CHECKSUMS.sha256": lines.append(f"{sha(os.path.join(dp, f))}  {os.path.relpath(os.path.join(dp, f), STIM).replace(os.sep, '/')}")
    open(os.path.join(STIM, "CHECKSUMS.sha256"), "w").write("\n".join(sorted(lines, key=lambda s: s.split('  ')[1])) + "\n"); print("checksums:", len(lines), "files")
def sheet(path, ids, seed, files):
    r = random.Random(seed); ids = list(ids); r.shuffle(ids)
    rows_to_csv(path, [{"stim_id": i, "image_file": files[i]} for i in ids], ["stim_id", "image_file", "label", "failure_category", "notes"])


PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Photo rating - RATER_NAME</title>
<style>body{font-family:Arial,sans-serif;max-width:900px;margin:12px auto;padding:0 12px}img{max-width:100%;max-height:62vh;display:block;margin:8px auto;border:1px solid #888}
button{font-size:17px;padding:10px 16px;margin:4px;cursor:pointer}.sel{outline:4px solid #1a7f37}.row{margin:8px 0}#bar{background:#ddd;height:10px}#fill{background:#1a7f37;height:10px;width:0}
small{color:#555}select,input[type=text]{font-size:16px;padding:6px}</style></head><body>
<h2>Is this a suitable crown/scalp photo? (RATER_NAME)</h2>
<small>Work alone, in the order shown. Read RATING_GUIDE.md first. This page never sends anything anywhere; your answers are saved in this browser and in the CSV you download.</small>
<div id="bar"><div id="fill"></div></div><p id="prog"></p>
<img id="im" alt="photo to rate">
<div class="row"><button id="b_suitable" onclick="setLabel('suitable')">suitable</button><button id="b_unsuitable" onclick="setLabel('unsuitable')">unsuitable</button><button id="b_ambiguous" onclick="setLabel('ambiguous')">ambiguous</button></div>
<div class="row">Main problem (only if unsuitable; optional guess if ambiguous): <select id="cat"><option value="">--</option><option>wrong_view</option><option>scalp_not_visible_or_too_small</option><option>blurry</option><option>too_dark_or_bright</option><option>obstructed</option><option>not_a_photo_or_multiple</option></select></div>
<div class="row">Notes (write <b>micro</b> for microscope close-ups, <b>hands</b> if hands are in the picture, or why you chose ambiguous): <input type="text" id="notes" size="60"></div>
<div class="row"><button onclick="go(-1)">&larr; Back</button><button onclick="go(1)">Next &rarr;</button><button onclick="dl()">Download my ratings (CSV)</button></div>
<p id="msg"></p>
<script>
var ITEMS=ITEMS_JSON, KEY="hsa_exp1_RATER_NAME_dev", i=0, A={};
try{A=JSON.parse(localStorage.getItem(KEY)||"{}")}catch(e){A={}}
function cur(){return ITEMS[i]}
function save(){var a=A[cur().id]||{};a.cat=document.getElementById("cat").value;a.notes=document.getElementById("notes").value;A[cur().id]=a;try{localStorage.setItem(KEY,JSON.stringify(A))}catch(e){}}
function setLabel(l){var a=A[cur().id]||{};a.label=l;A[cur().id]=a;save();show()}
function show(){var it=cur(),a=A[it.id]||{};document.getElementById("im").src=it.file;
 ["suitable","unsuitable","ambiguous"].forEach(function(l){document.getElementById("b_"+l).className=(a.label==l)?"sel":""});
 document.getElementById("cat").value=a.cat||"";document.getElementById("notes").value=a.notes||"";
 var done=ITEMS.filter(function(x){return A[x.id]&&A[x.id].label}).length;
 document.getElementById("prog").innerText="Photo "+(i+1)+" of "+ITEMS.length+"  |  rated: "+done;document.getElementById("fill").style.width=(100*done/ITEMS.length)+"%"}
function go(d){save();var n=i+d;if(n>=0&&n<ITEMS.length){i=n;show()}}
function dl(){save();var miss=ITEMS.filter(function(x){return !(A[x.id]&&A[x.id].label)}).length;
 var rows=["stim_id,image_file,label,failure_category,notes"];
 ITEMS.forEach(function(x){var a=A[x.id]||{};var cat=a.cat||"";if(a.label=="suitable")cat="none";
  rows.push([x.id,x.rel,a.label||"",cat,'"'+(a.notes||"").replace(/"/g,'""')+'"'].join(","))});
 var b=new Blob([rows.join("\\n")+"\\n"],{type:"text/csv"}),u=URL.createObjectURL(b),l=document.createElement("a");l.href=u;l.download="rating_dev_RATER_NAME_DONE.csv";l.click();
 document.getElementById("msg").innerText=miss?("Downloaded, but "+miss+" photos are still unrated."):"Downloaded. All photos rated. Move the file into the research/exp1/private folder and do not edit it."}
show();
</script></body></html>"""
def rating_page(path, ids, seed, files, rater):
    r = random.Random(seed); ids = list(ids); r.shuffle(ids)
    items = [{"id": i, "file": "../stimuli/" + files[i], "rel": files[i]} for i in ids]
    import json
    open(path, "w", encoding="utf-8").write(PAGE.replace("RATER_NAME", rater).replace("ITEMS_JSON", json.dumps(items)))


def choose(sc, ba, seed, faces=0):
    """The ONLY place that decides which photos go where (also used by verify_disjoint.py --simulate, which needs no images)."""
    fs = sc[sc["split"] == "test"]
    out = {"final_scalp": fs, "final_faces": ba.iloc[0:0], "dev_faces": ba.iloc[0:0]}
    if faces:
        bt = ba[ba["split"] == "test"]
        out["final_faces"] = pd.concat([bt[bt["balding"] == lab].sample(faces // 2, random_state=seed) for lab in (1, 0)])
        out["dev_faces"] = ba[ba["split"] == "train"].sample(max(2, faces // 3), random_state=seed)
    dev = [sc[(sc["split"] == "train") & (sc["source"] == s)].sample(12, random_state=seed) for s in ("roboflow_hairdata", "healthy_scalp", "extra_dandruff_big_chunks")]
    out["dev_scalp"] = pd.concat(dev); out["dev_syn_originals"] = dev[0].iloc[:4]
    return out

def phase1(a):
    rng = random.Random(a.seed)
    sc = pd.read_csv(os.path.join(ROOT, "data", "scalp_labels.csv")); ba = pd.read_csv(os.path.join(ROOT, "data", "balding_labels.csv"))
    pub, priv, files = [], [], {}
    def add(setname, im, src, row, kind="natural", vt="", sev="", exp="", expc="", orig=None):
        s = sid(a.seed, setname, row["filepath"], vt, sev); f = save(im, setname, s); files[s] = f
        pub.append({"stim_id": s, "set": setname, "file": f})
        priv.append({"stim_id": s, "set": setname, "file": f, "kind": kind, "source": src, "orig_split": row["split"], "filepath": row["filepath"], "group": row.get("group", ""), "original_id": orig or s,
                     "variant_type": vt, "severity": sev, "expected_label": exp, "expected_category": expc})
    c = choose(sc, ba, a.seed, a.faces); everything = (a.scope == "all")
    if everything:  # final photos are generated ONLY with --scope all (not approved yet)
        for _, r in c["final_scalp"].iterrows(): add("final_natural", load(a.raw, r.filepath), r.source, r)
        for _, r in c["final_faces"].iterrows(): add("final_natural", load(a.raw, r.filepath), "kaggle_balding", r)
    oid = {}
    for _, r in c["dev_scalp"].iterrows(): add("dev", load(a.raw, r.filepath), r.source, r); oid[r.filepath] = priv[-1]["stim_id"]
    for _, r in c["dev_faces"].iterrows(): add("dev", load(a.raw, r.filepath), "kaggle_balding", r)
    for _, r in (c["dev_syn_originals"] if everything else c["dev_syn_originals"].iloc[0:0]).iterrows():
        for kind in ("blur", "dark", "wide", "obstruct"):
            add("dev", degrade(load(a.raw, r.filepath), kind, 1, rng), r.source, r, "synthetic_unverified_original", kind, "severe", "unsuitable", SYN_EXPECT[kind], orig=oid[r.filepath])
    rows_to_csv(os.path.join(STIM, "manifest_public.csv"), pub, PCOLS); rows_to_csv(os.path.join(PRIV, "manifest_private.csv"), priv, VCOLS)
    fin = [p["stim_id"] for p in priv if p["set"] == "final_natural"]; dev = [p["stim_id"] for p in priv if p["set"] == "dev" and p["kind"] == "natural"]
    if everything:
        sheet(os.path.join(PRIV, "rating_final_rater1.csv"), fin, a.seed + 1, files); sheet(os.path.join(PRIV, "rating_final_rater2.csv"), fin, a.seed + 2, files)
    sheet(os.path.join(PRIV, "rating_dev_rater1.csv"), dev, a.seed + 3, files); sheet(os.path.join(PRIV, "rating_dev_rater2.csv"), dev, a.seed + 4, files)
    for rn, sd in (("rater1", a.seed + 3), ("rater2", a.seed + 4)): rating_page(os.path.join(PRIV, f"rate_dev_{rn}.html"), dev, sd, files, rn)
    write_checksums()
    print("final_natural", len(fin), "| dev natural", len(dev), "| dev synthetic", sum(p["kind"].startswith("synthetic") for p in priv))

def phase2(a):
    rng = random.Random(a.seed + 99)
    pm = pd.read_csv(os.path.join(PRIV, "manifest_private.csv"), dtype=str).fillna("")
    r1 = pd.read_csv(os.path.join(PRIV, "rating_final_rater1.csv"), dtype=str).fillna(""); r2 = pd.read_csv(os.path.join(PRIV, "rating_final_rater2.csv"), dtype=str).fillna("")
    adj = os.path.join(PRIV, "adjudication.csv"); aj = pd.read_csv(adj, dtype=str).fillna("").set_index("stim_id")["label"].to_dict() if os.path.exists(adj) else {}
    m = r1.merge(r2, on="stim_id", suffixes=("_1", "_2")); m["final"] = [aj.get(s, a1 if a1 == b1 else "ambiguous") for s, a1, b1 in zip(m.stim_id, m.label_1, m.label_2)]
    ok = m[m.final == "suitable"].merge(pm[["stim_id", "source", "filepath", "group", "orig_split"]], on="stim_id")
    ok = ok[ok.source != "kaggle_balding"]
    per = max(1, 30 // max(1, ok.source.nunique())); chosen = pd.concat([g.sample(min(per, len(g)), random_state=a.seed) for _, g in ok.groupby("source")])
    pub, priv = [], []
    for _, o in chosen.iterrows():
        for kind in SYN:
            for sev in (0, 1):
                sv = "moderate" if sev == 0 else "severe"; s = sid(a.seed, "final_synth", o.filepath, kind, sv)
                f = save(degrade(load(a.raw, o.filepath), kind, sev, rng), "final_synth", s)
                pub.append({"stim_id": s, "set": "final_synth", "file": f})
                priv.append({"stim_id": s, "set": "final_synth", "file": f, "kind": "synthetic", "source": o.source, "orig_split": o.orig_split, "filepath": o.filepath, "group": o.group, "original_id": o.stim_id,
                             "variant_type": kind, "severity": sv, "expected_label": "unsuitable" if sv == "severe" else "graded", "expected_category": SYN_EXPECT[kind]})
    mp = pd.read_csv(os.path.join(STIM, "manifest_public.csv"), dtype=str); mp = mp[mp["set"] != "final_synth"]
    rows_to_csv(os.path.join(STIM, "manifest_public.csv"), list(mp.to_dict("records")) + pub, PCOLS)
    old = pm[pm["set"] != "final_synth"]; rows_to_csv(os.path.join(PRIV, "manifest_private.csv"), list(old.to_dict("records")) + priv, VCOLS)
    rows_to_csv(os.path.join(PRIV, "spot_check_rater1.csv"), [{"stim_id": p["stim_id"], "image_file": p["file"], "label": "", "failure_category": "", "notes": ""} for p in rng.sample([p for p in priv if p["severity"] == "severe"], max(1, len([p for p in priv if p["severity"] == "severe"]) // 5))], ["stim_id", "image_file", "label", "failure_category", "notes"])
    write_checksums(); print("synthetic originals", len(chosen), "variants", len(priv))

if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("--raw", required=True); p.add_argument("--phase", default="natural", choices=["natural", "synthetic"]); p.add_argument("--seed", type=int, default=42); p.add_argument("--scope", default="dev", choices=["dev", "all"], help="dev (default) = only the 36 development photos; all = also the final evaluation photos (NOT approved yet)"); p.add_argument("--faces", type=int, default=0, help="number of face photos for the optional easy stratum (default 0 = none; see DATA_LICENCE_PRIVACY_REVIEW.md)")
    a = p.parse_args(); (phase1 if a.phase == "natural" else phase2)(a)
