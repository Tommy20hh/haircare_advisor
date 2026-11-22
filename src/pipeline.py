"""
The decision pipeline behind the service (one photo, one model).

    photo -> quality flags + familiarity ("is it the kind of photo the AI was trained on?")
          -> status: match | partial | mismatch
          -> (unless mismatch) the model + a stability check -> one verdict per condition
"""

from inference import familiarity, image_quality, predict_stable
from verdict import decide, mismatch_verdict, photo_status, quality_flags


def assess(bundle, image) -> dict:
    """Returns {status, tier, fam, flags, results, verdicts}.
    For a 'mismatch' photo the model is NOT run: every condition is 'unsuitable'."""
    flags = quality_flags(image_quality(image))
    fam = familiarity(bundle, image)
    tier = fam["tier"] if fam else None
    status = photo_status(tier, flags)
    out = {"status": status, "tier": tier, "fam": fam, "flags": flags, "results": None, "verdicts": None}
    if status == "mismatch":
        out["verdicts"] = {name: mismatch_verdict(flags) for name in bundle.class_names}
        return out
    results = predict_stable(bundle, image)
    out["results"] = results
    out["verdicts"] = {name: decide(info, tier, flags) for name, info in results.items()}
    return out
