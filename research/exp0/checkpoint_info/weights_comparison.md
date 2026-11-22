# Kaggle checkpoint vs deployed checkpoint

Method: each `.pt` is a zip archive. For every tensor-data entry (`*/data/<n>`) the stored CRC-32 was compared between the Kaggle-run file (`v4_results/checkpoints`) and the deployed file (`checkpoints/`). Entry counts: balding 626, scalp 1882.

Result: **all tensor CRCs identical for both models.** The files differ in SHA-256 because the deployed copies also carry the familiarity gate written into the same file (`scripts/build_gate.py`, "writes the gate INTO the checkpoint file") and other pickle metadata. CRC-32 is a consistency check, not a cryptographic proof; the reproduced metrics (identical to the Kaggle run to the logged precision) are the stronger confirmation.
