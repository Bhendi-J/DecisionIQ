"""Fine-tune DistilBERT; labels must be 0=legitimate, 1=phishing."""

import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True, help="CSV with text and label columns")
    parser.add_argument("--epochs", type=float, default=1)
    parser.add_argument("--sample-size", type=int, default=0, help="0 uses the complete dataset")
    args = parser.parse_args()
    import numpy as np
    import pandas as pd
    from datasets import Dataset
    from sklearn.metrics import accuracy_score, precision_recall_fscore_support
    from sklearn.model_selection import train_test_split
    from transformers import (
        AutoModelForSequenceClassification,
        AutoTokenizer,
        Trainer,
        TrainingArguments,
    )

    from decisioniq.config import configured_path

    frame = pd.read_csv(args.data)[["text", "label"]].dropna()
    if set(frame["label"].unique()) != {0, 1}:
        parser.error("Dataset labels must contain exactly 0=legitimate and 1=phishing")
    if args.sample_size:
        if args.sample_size < 20 or args.sample_size >= len(frame):
            parser.error("Sample size must be at least 20 and smaller than the dataset")
        frame, _ = train_test_split(
            frame, train_size=args.sample_size, stratify=frame.label, random_state=42
        )
    train, test = train_test_split(frame, test_size=0.2, stratify=frame.label, random_state=42)
    train, validation = train_test_split(
        train, test_size=0.1, stratify=train.label, random_state=42
    )
    tokenizer = AutoTokenizer.from_pretrained("distilbert-base-uncased")
    model = AutoModelForSequenceClassification.from_pretrained(
        "distilbert-base-uncased",
        num_labels=2,
        id2label={0: "legitimate", 1: "phishing"},
        label2id={"legitimate": 0, "phishing": 1},
    )

    def dataset(data):
        return Dataset.from_pandas(data, preserve_index=False).map(
            lambda rows: tokenizer(
                rows["text"], truncation=True, padding="max_length", max_length=256
            ),
            batched=True,
        )

    def metrics(prediction):
        logits, labels = prediction
        predicted = np.argmax(logits, axis=-1)
        precision, recall, f1, _ = precision_recall_fscore_support(
            labels,
            predicted,
            average="binary",
            zero_division=0,
        )
        return {
            "accuracy": accuracy_score(labels, predicted),
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }

    path = configured_path("PHISHING_MODEL_PATH", "services/phishing/models/phishing_distilbert")
    training = TrainingArguments(
        output_dir=str(path),
        eval_strategy="epoch",
        save_strategy="epoch",
        learning_rate=2e-5,
        per_device_train_batch_size=4,
        per_device_eval_batch_size=4,
        num_train_epochs=args.epochs,
        weight_decay=0.01,
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        report_to="none",
        seed=42,
        save_total_limit=1,
    )
    trainer = Trainer(
        model=model,
        args=training,
        train_dataset=dataset(train),
        eval_dataset=dataset(validation),
        processing_class=tokenizer,
        compute_metrics=metrics,
    )
    trainer.train()
    print(trainer.evaluate(dataset(test)))
    trainer.save_model(str(path))
    tokenizer.save_pretrained(path)
    print(f"Saved model and tokenizer to {path}")


if __name__ == "__main__":
    main()
