# Care rules (rule-based, not machine learning)

The care ideas are fixed texts chosen by rules, not generated. That makes them auditable and unable to hallucinate.
Rules live in `advice_keys()` in `src/verdict.py`; the wording in `web/data/i18n.json` (keys `tip_*`, `multi`, `general`, `retake`, `not_assessed`).

| Situation | Advice shown |
|---|---|
| verdict `unsure` or `unsuitable` for a condition | `retake`: result not reliable, retake the photo or have it checked in person |
| verdict `possible` for a condition | `tip_<condition>`: one general, non-medical habit + when to see a doctor |
| two or more `possible` | `multi`: show it to a dermatologist |
| every assessed condition `none_seen` | `general`: general hair-care habits |
| a photo slot left empty | `not_assessed` |

No rule gives a diagnosis, a dose or a product recommendation beyond naming a common ingredient class.
