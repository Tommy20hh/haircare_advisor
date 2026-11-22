"""
Turns raw model output into one plain verdict per condition. No torch needed, so it
is easy to test. The rules are deliberately cautious: a low score is NEVER allowed to
become a reassuring "all clear" when the photo is unfamiliar, unsharp, or the answer
changes when the photo is nudged.

verdict keys:
    possible   - the model sees a possible sign
    none_seen  - no clear sign seen (NOT proof that nothing is there)
    unsure     - can't tell
    unsuitable - this photo can't be judged (too different from what the AI learned)
reliability keys: good | limited | low
reason keys (for the "why" line): unfamiliar, very_unfamiliar, blurry, dark, bright, small,
                                  unstable, close_call, no_gate, blank
"""

from typing import Dict, List, Optional

# All numbers live in settings.py. PHONE_VALIDATED stays a module attribute so tests can switch it.
from settings import (MIN_SIDE_PX, PHONE_VALIDATED, SPREAD_SHAKY, SPREAD_UNSTABLE,  # noqa: F401
                      TOO_BLURRY, TOO_BRIGHT, TOO_DARK, BLANK_SHARPNESS)


def quality_flags(q: Optional[dict]) -> List[str]:
    if not q:
        return []
    flags = []
    if min(q.get("width", 999), q.get("height", 999)) < MIN_SIDE_PX:
        flags.append("small")
    b = q.get("brightness", 128)
    if b < TOO_DARK:
        flags.append("dark")
    elif b > TOO_BRIGHT:
        flags.append("bright")
    sh = q.get("sharpness", 999)
    if sh < BLANK_SHARPNESS:
        flags.append("blank")
    if sh < TOO_BLURRY:
        flags.append("blurry")
    return flags


def photo_status(tier: Optional[str], flags: List[str]) -> str:
    """The front-door check: is this the kind of photo the AI was trained on?
    match    - looks like the training photos and is sharp/bright enough
    partial  - somewhat different or low quality: answers are shown as a rough hint only
    mismatch - very different: the app refuses to judge it"""
    if tier == "very_unfamiliar" or "blank" in flags:
        return "mismatch"
    if tier == "familiar" and not flags:
        return "match"
    return "partial"


def mismatch_verdict(flags: List[str]) -> Dict:
    return {"verdict": "unsuitable", "reliability": "low", "reasons": ["very_unfamiliar"] + list(flags)}


def summary_groups(verdicts: Dict[str, Dict], not_assessed: List[str]) -> Dict[str, List[str]]:
    """Condition names grouped by verdict, for the one-line summary at the top of the results."""
    groups: Dict[str, List[str]] = {"possible": [], "unsure": [], "none_seen": [], "unsuitable": []}
    for name, v in verdicts.items():
        if name not in not_assessed:
            groups[v["verdict"]].append(name)
    return groups


def decide(info: dict, tier: Optional[str], flags: List[str]) -> Dict:
    out = _decide(info, tier, flags)
    if out["reliability"] == "good" and not PHONE_VALIDATED:
        out = dict(out, reliability="limited", reasons=out["reasons"] + ["untested"])
    return out


def _decide(info: dict, tier: Optional[str], flags: List[str]) -> Dict:
    """info: {'status': True/False/None, 'spread': float (optional)}; tier: familiar|unfamiliar|very_unfamiliar|None."""
    reasons: List[str] = []
    spread = info.get("spread", 0.0)

    if tier == "very_unfamiliar":
        return {"verdict": "unsuitable", "reliability": "low", "reasons": ["very_unfamiliar"] + flags}

    weak_photo = tier in ("unfamiliar", None) or any(f in flags for f in ("blurry", "dark", "bright", "small"))
    if tier == "unfamiliar":
        reasons.append("unfamiliar")
    reasons += [f for f in flags]
    if tier is None:
        reasons.append("no_gate")

    status = info.get("status")
    if status is None:
        return {"verdict": "unsure", "reliability": "low", "reasons": reasons + ["close_call"]}
    if spread > SPREAD_UNSTABLE:
        return {"verdict": "unsure", "reliability": "low", "reasons": reasons + ["unstable"]}

    if status is False:
        if weak_photo:  # never reassure on a weak photo
            return {"verdict": "unsure", "reliability": "low", "reasons": reasons}
        rel = "good" if (tier == "familiar" and spread <= SPREAD_SHAKY) else "limited"
        return {"verdict": "none_seen", "reliability": rel, "reasons": reasons}

    rel = "good" if (tier == "familiar" and not weak_photo and spread <= SPREAD_SHAKY) else "limited"
    if spread > SPREAD_SHAKY:
        reasons.append("unstable")
    return {"verdict": "possible", "reliability": rel, "reasons": reasons}


def advice_keys(verdicts: Dict[str, Dict], not_assessed: List[str]) -> List[str]:
    """Language-neutral list of advice items; the app maps each key to text."""
    keys: List[str] = []
    assessed = {k: v for k, v in verdicts.items() if k not in not_assessed}
    for name, v in assessed.items():
        if v["verdict"] in ("unsure", "unsuitable"):
            keys.append(f"retake:{name}")
    for name, v in assessed.items():
        if v["verdict"] == "possible":
            keys.append(f"tip:{name}")
    positives = [n for n, v in assessed.items() if v["verdict"] == "possible"]
    if len(positives) >= 2:
        keys.append("multi")
    if assessed and all(v["verdict"] == "none_seen" for v in assessed.values()):
        keys.append("general")
    if not_assessed:
        keys.append("not_assessed")
    return keys
