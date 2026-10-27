"""Evaluate the export on the test split reconstructed from the contributor's script.

Writes aggregate metrics only. No raw email text is exported or sent to an external service.
"""

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path


def evaluate(data, batch_size=16):
    import numpy as np
    import pandas as pd
    import torch
    from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support
    from sklearn.model_selection import train_test_split

    from decisioniq.config import ROOT, configured_path
    from services.phishing.predict import MAX_TOKENS, _load_bundle

    frame = pd.read_csv(data, usecols=["text", "label"])
    if len(frame) <= 10000 or frame.isna().any().any() or set(frame.label.unique()) != {0, 1}:
        raise ValueError(
            "Use the complete, non-null binary-label CEAS08 CSV from the contributor branch"
        )
    sampled, _ = train_test_split(frame, train_size=10000, stratify=frame.label, random_state=42)
    training, test = train_test_split(
        sampled, test_size=0.20, stratify=sampled.label, random_state=42
    )
    training, validation = train_test_split(
        training, test_size=0.10, stratify=training.label, random_state=42
    )
    tokenizer, model = _load_bundle()
    probabilities = []
    for start in range(0, len(test), batch_size):
        inputs = tokenizer(
            test.text.iloc[start : start + batch_size].tolist(),
            return_tensors="pt",
            truncation=True,
            padding=True,
            max_length=MAX_TOKENS,
        )
        with torch.inference_mode():
            values = torch.softmax(model(**inputs).logits, dim=-1)[:, 1].tolist()
        probabilities.extend(values)
        if start // batch_size % 20 == 0:
            print(
                f"Evaluated {min(start + batch_size, len(test))}/{len(test)} messages", flush=True
            )
    predicted = np.asarray(probabilities) >= 0.5
    actual = test.label.to_numpy(dtype=int)

    def metrics(mask):
        a, p = actual[mask], predicted[mask]
        if not len(a):
            return {"count": 0, "message": "No independent records remain after overlap filtering"}
        precision, recall, f1, _ = precision_recall_fscore_support(
            a, p, average="binary", zero_division=0
        )
        return {
            "count": len(a),
            "accuracy": float(accuracy_score(a, p)),
            "phishing_precision": float(precision),
            "phishing_recall": float(recall),
            "phishing_f1": float(f1),
            "confusion_matrix": confusion_matrix(a, p, labels=[0, 1]).tolist(),
            "confusion_matrix_order": "rows=actual [legitimate, phishing]; columns=predicted [legitimate, phishing]",
        }

    def normalized(series):
        return series.str.casefold().str.replace(r"\s+", " ", regex=True).str.strip()

    exposed = set(normalized(pd.concat([training.text, validation.text])))
    normalized_test = normalized(test.text)
    strict_mask = (~normalized_test.isin(exposed) & ~normalized_test.duplicated()).to_numpy()
    model_path = (
        configured_path("PHISHING_MODEL_PATH", "services/phishing/models/phishing_distilbert")
        / "model.safetensors"
    )
    with Path(data).open("rb") as stream:
        data_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    with model_path.open("rb") as stream:
        model_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    manifest = json.loads((ROOT / "services/phishing/model_manifest.json").read_text())
    return {
        "model_sha256": model_hash,
        "runtime_versions": {
            name: importlib.metadata.version(name)
            for name in ["torch", "transformers", "tokenizers", "scikit-learn", "pandas"]
        },
        "contributor_revision": manifest["revision"]
        if model_hash
        == next(f["sha256"] for f in manifest["files"] if f["name"] == "model.safetensors")
        else None,
        "dataset_sha256": data_hash,
        "dataset_rows": len(frame),
        "sampled_rows": len(sampled),
        "training_rows": len(training),
        "validation_rows": len(validation),
        "reconstructed_test": metrics(np.ones(len(test), dtype=bool)),
        "overlap_filtered_test": metrics(strict_mask),
        "test_rows_matching_training_or_validation": int(normalized_test.isin(exposed).sum()),
        "max_tokens": MAX_TOKENS,
        "phishing_threshold": 0.5,
        "batch_size": batch_size,
        "limitations": [
            "The split is reconstructed from the supplied train.py (10,000 sampled rows, seed 42). The actual training lineage is not independently certified.",
            "Overlap filtering removes normalized exact text matches, not near duplicates or shared email threads.",
            "This is one source and one random split, not an external, temporal, or company-specific validation.",
            "Phishing scores are model outputs, not calibrated probabilities of organizational compromise.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("outputs/phishing-evaluation.json"))
    parser.add_argument("--batch-size", type=int, default=16, choices=range(1, 65))
    args = parser.parse_args()
    result = evaluate(args.data, args.batch_size)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
