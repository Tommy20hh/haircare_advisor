"""
Every tunable number of the app in ONE place (no torch needed).

Change a value here, not inside verdict.py / inference.py / the app.
"""

MODEL_VERSION = "4.1"

# Flip to True ONLY after the models have been measured on real phone photos.
# While False, no verdict may be labelled "good" reliability (training photos are stock/close-up/screenshots).
PHONE_VALIDATED = False

# Stability check: probabilities of ONE photo and slightly changed copies of it
SPREAD_UNSTABLE = 0.30   # larger gap -> "not sure"
SPREAD_SHAKY = 0.15      # larger gap -> reliability "limited"
STABILITY_ZOOMS = (0.85, 0.7)   # centre crops used besides the original and its mirror image

# Photo-quality limits
MIN_SIDE_PX = 200        # shorter side below this -> "small"
TOO_DARK = 60            # mean grey level below this -> "dark"
TOO_BRIGHT = 205         # mean grey level above this -> "bright"
TOO_BLURRY = 40          # variance of the Laplacian below this -> "blurry"
BLANK_SHARPNESS = 2      # almost no detail at all (plain colour, blank wall) -> "blank": refused, never judged

MAX_UPLOAD_SIDE = 1024   # photos are shrunk to this for speed (EXIF rotation is applied first)

# Web service (service/main.py)
APP_VERSION = "1.1.0"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024          # per photo
MAX_REQUEST_BYTES = 2 * MAX_UPLOAD_BYTES + 1024 * 1024   # whole upload request (two photos + form fields)
MAX_IMAGE_PIXELS = 40_000_000                # refuse "decompression bombs": small file, enormous picture
MIN_UPLOAD_SIDE = 64
ALLOWED_TYPES = ("image/jpeg", "image/png", "image/webp")   # what the browser says the file is
ALLOWED_FORMATS = ("JPEG", "MPO", "PNG", "WEBP")            # what the file really is (MPO = JPEG variant some phones write)

# The two photo slots and the model + conditions behind each. The ids "front" / "crown" match i18n keys.
SLOTS = {
    "front": {"task": "balding", "conditions": ["balding"]},
    "crown": {"task": "scalp", "conditions": ["dryness", "dandruff", "low_density"]},
}
