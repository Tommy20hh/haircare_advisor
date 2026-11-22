"""Checks files against a sha256 list (lines: '<hash>  <relative path>'). Works on Windows, Linux and Kaggle (standard library only).
  python verify_checksums.py <folder> <checksum_file>"""
import hashlib, os, sys
folder, lst = sys.argv[1], sys.argv[2]; bad = ok = 0
for line in open(lst, encoding="utf-8"):
    if not line.strip(): continue
    h, rel = line.rstrip("\n").split("  ", 1); p = os.path.join(folder, rel)
    if not os.path.exists(p): print("MISSING", rel); bad += 1; continue
    d = hashlib.sha256(open(p, "rb").read()).hexdigest()
    if d == h: ok += 1
    else: print("MISMATCH", rel); bad += 1
print(f"{ok} ok, {bad} problems"); sys.exit(1 if bad else 0)
