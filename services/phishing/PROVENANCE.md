# Trained phishing artifact

Integrated on 27 October 2026 from [Bhendi-J/DecisionIQ, email_phishing_detection](https://github.com/Bhendi-J/DecisionIQ/tree/40043eacb0bc0151d0a295667b993fee0a199957/model/phishing_distilbert), commit `40043eacb0bc0151d0a295667b993fee0a199957`.

The export is DistilBERT for binary sequence classification (66,955,010 parameters, float32). Required files are `model.safetensors`, `config.json`, `tokenizer.json`, and `tokenizer_config.json`. The weight file is 267,832,560 bytes (about 268 MB); the complete inference export totals 268,545,235 bytes. Training arguments and training datasets are excluded from installation. We integrated the supplied weights unchanged; we did not retrain them.

`model_manifest.json` records pinned source paths, sizes, and SHA-256 hashes. The installer verifies bytes before publishing the model directory, reuses a verified Git LFS object when possible, and otherwise downloads from the commit-pinned GitHub URLs. A 134-byte Git LFS pointer is not a model and fails size/hash verification. The model directory is ignored by Git; source archives stay small and installation is reproducible.

The configuration uses generic `LABEL_0` and `LABEL_1` names. The semantic interpretation comes from the contributor's `predict.py`: class 1 is phishing; class 0 is legitimate. The integrated service preserves that interpretation, the 0.5 threshold, and the 256-token inference limit. It runs locally, without downloading models during prediction or transmitting emails to an external inference provider.

## Reconstructed source evaluation

The supplied `train.py` samples 10,000 records with stratification and seed 42, reserves 20% for testing, then takes 10% of the remaining records for validation. This gives 7,200 training, 800 validation, and 2,000 test messages. It configures one epoch and selects the best validation-F1 checkpoint.

We reproduced those splits from the branch's `data/CEAS08_DecisionIQ_clean.csv` (34,390 rows; SHA-256 `4793ba3dbbba52b44ec84819ef5e23ab63e373273568bdfd57ac7206fbca51a4`) and evaluated the downloaded model locally. Aggregate results and runtime versions are in `evaluation.json`.

| Measure | Result |
| --- | --- |
| Evaluated messages | 2,000 |
| Accuracy | 99.00% |
| Phishing precision | 99.49% |
| Phishing recall | 98.50% |
| Phishing F1 | 98.99% |
| True legitimate / false alarms | 997 / 5 |
| Missed phishing / correctly flagged phishing | 15 / 983 |
| Test messages exactly matching normalized training/validation text | 0 |

This is a reconstructed held-out split according to the supplied script, not independently certified training lineage. It is not a separate external, temporal, or organization-specific benchmark. Normalized exact-match checking does not detect near duplicates or shared email threads. Scores are classifier outputs rather than calibrated probabilities of compromise.

A separate smoke example containing an urgent short account-suspension/password-verification lure received a phishing score near 1/100 and was not flagged. That miss is recorded here alongside the strong same-source test result. ForeSight therefore describes a negative result as **No phishing flag**, and explicitly notes that unflagged messages can still be malicious. Inputs beyond the first 256 tokens are excluded and the UI exposes truncation.

To reproduce:

```bash
uv run --extra phishing python -m scripts.evaluate_phishing_model --data /path/to/CEAS08_DecisionIQ_clean.csv
```

Only aggregate metrics are written; the evaluation command does not export raw email text. The source CSV is not included in the clean application package.
