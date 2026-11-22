"""Website checks: every i18n key used by the pages / app.js exists, EN and TH have identical keys,
JavaScript parses, local asset links exist. Run: python tests/test_web.py"""
import json
import os
import re
import subprocess

W = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "web")
d = json.load(open(os.path.join(W, "data", "i18n.json"), encoding="utf-8"))
assert set(d["en"]) == set(d["th"]), set(d["en"]) ^ set(d["th"])
PAGES = ("index.html", "check.html", "details.html", "monitoring.html")
html = "".join(open(os.path.join(W, f), encoding="utf-8").read() for f in PAGES)
js = open(os.path.join(W, "js", "app.js"), encoding="utf-8").read()
used = set(re.findall(r'data-i18n(?:-list)?="([^"]+)"', html)) | set(re.findall(r'\bt\("([a-z0-9_]+)"', js))
conds = ("balding", "dryness", "dandruff", "low_density")
verd = ("possible", "none_seen", "unsure", "unsuitable")
dyn = {f"{p}{c}" for p in ("cond_", "what_", "tip_") for c in conds} | {f"{p}{v}" for p in ("v_", "m_", "next_") for v in verd}
dyn |= {f"res_{p}_{v}" for p in ("h", "s") for v in verd}
dyn |= {f"rel_{r}" for r in ("good", "limited", "low")} | {f"pc_{s}" for s in ("match", "partial", "mismatch")}
dyn |= {f"why_{r}" for r in ("unfamiliar", "very_unfamiliar", "blurry", "dark", "bright", "small", "blank", "unstable", "close_call", "untested", "no_gate")}
dyn |= {f"err_{c}" for c in ("no_photo", "unsupported_type", "too_large", "too_many_pixels", "unreadable", "empty_file", "too_small", "model_missing", "bad_request", "network", "timeout", "server_error", "other")}
missing = [k for k in used | dyn if not k.endswith("_") and k not in d["en"]]
assert not missing, missing
r = subprocess.run(["node", "--check", os.path.join(W, "js", "app.js")], capture_output=True, text=True)
assert r.returncode == 0, r.stderr
for a in re.findall(r'(?:src|href)="((?:assets|css|js)/[^"]+)"', html):
    assert os.path.exists(os.path.join(W, a)), a

# --- the pages must work under the strict Content-Security-Policy the service sends (and contact no other website) ---
css = open(os.path.join(W, "css", "site.css"), encoding="utf-8").read()
assert not re.search(r'(?:src|href|action)\s*=\s*"(?:https?:)?//', html), "a page links to another website"
assert not re.search(r'url\(\s*["\']?(?:https?:)?//', css), "the stylesheet loads something from another website"
assert not re.search(r'(?:fetch|import|XMLHttpRequest)[^;\n]*["\']https?://', js), "the script talks to another website"
assert " style=" not in html and 'style=\\"' not in js and "style='" not in js and "<style" not in html, "inline styles are blocked by the content policy"
assert not re.search(r'<script(?![^>]*\bsrc=)', html), "inline script is blocked by the content policy"
assert not re.search(r'\son(?:click|change|load|error|submit|input)\s*=', html + js), "inline event handlers are blocked by the content policy"
assert "eval(" not in js and "new Function" not in js
for f in re.findall(r"url\(\.\./(fonts/[^)]+)\)", css):
    assert os.path.exists(os.path.join(W, f)), "missing font file " + f
print("web tests passed")
