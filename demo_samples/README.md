# Demo photos

Put 12-15 photos here (the website shows them under "Try a sample photo"):

| Name pattern | What | How many |
|---|---|---|
| `front_01.jpg` ... | front photo, head straight, hairline visible | 3 |
| `dandruff_01.jpg` ... | close-up top-of-head scalp with flakes | 3 |
| `dryness_01.jpg` ... | close-up dry scalp | 3 |
| `density_01.jpg` ... | close-up thin / sparse hair | 3 |
| `bad_01.jpg` ... | wrong type on purpose (selfie, room, hat) to show the refusal | 3 |

Names starting with `front` go to the front slot, everything else to the top-of-head slot.

Rules: free-licence photos only (Wikimedia Commons, Unsplash, Pexels; check each licence), no identifiable faces unless the
licence clearly allows it, and run `python scripts/check_demo_photos.py` so none is a near-copy of a training image.
Labels are NOT ground truth: nobody has confirmed what each photo shows. Say so in the demo.

Optional `manifest.json` for credits:
```json
{ "dandruff_01.jpg": {"label": "Dandruff, close-up", "source": "Wikimedia Commons, author name", "licence": "CC BY 4.0"} }
```
