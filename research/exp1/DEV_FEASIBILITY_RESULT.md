# Development-set feasibility result (2026-11-23)
Rater: the project owner only (one rater; no agreement number). 36 dev photos (12 per source), seed 42. Counts only; no photos are stored here.
```
source                         n  unsuit.  ambig.  micro?   projected unsuitable among test photos (95% range)
roboflow_hairdata             12        5       0       0    15.4  (7 - 25) of 37
healthy_scalp                 12        0       0       0     0.0  (0 - 16) of 68
extra_dandruff_big_chunks     12        3       0       0    17.2  (6 - 37) of 69
Projected CLEARLY unsuitable photos among the 174: about 33 (rough range 13 - 78); ambiguous would add about 0.
Rule R1 needs at least 30 consensus-unsuitable photos.
Planning signal: UNCERTAIN - cannot tell from 36 photos
```
Main problems recorded for the 8 unsuitable photos: hairdata 5 x wrong_view; extra_dandruff 2 x scalp_not_visible_or_too_small, 1 x wrong_view; healthy_scalp none.
## Reading
- Point estimate (about 33) is just above R1's 30, but the range (13-78) is far too wide to say R1 will be met. Wilson ranges from 12 photos per source are wide by construction.
- Single rater, zero ambiguous answers, and no `micro` notes were recorded: the sheet probably under-uses `ambiguous`, so consensus numbers with two raters may differ.
- Natural failures seen are almost only wrong_view / too small. No naturally blurry, dark or obstructed photo appeared in the 36; those categories rely on the synthetic stratum (technical stress only).
- `healthy_scalp` (68 of 174) contributes 0 in the sample; if the real 68 contain unsuitable photos the total rises.
- This does not change R1 (not relaxed after the fact). The actual count is only known after the 174 final photos are rated by two raters, before any VLM run.
