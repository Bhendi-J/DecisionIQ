import pandas as pd
import numpy as np

from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support
)

from datasets import Dataset

from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer
)

# 1. LOAD DATASET
df = pd.read_csv("data/CEAS08_DecisionIQ_clean.csv")
print("Original dataset:")
print(df["label"].value_counts())

# 2. OPTIONAL: SMALL SAMPLE FOR CPU TESTING
# Remove this section later when you want to train on the complete dataset.

df, _ = train_test_split(
    df,
    train_size=10000,
    random_state=42,
    stratify=df["label"]
)

print("\nDataset used for this training run:")
print(df["label"].value_counts())

# 3. TRAIN / TEST SPLIT
train_df, test_df = train_test_split(
    df,
    test_size=0.20,
    random_state=42,
    stratify=df["label"]
)

# 4. TRAIN / VALIDATION SPLIT
train_df, val_df = train_test_split(
    train_df,
    test_size=0.10,
    random_state=42,
    stratify=train_df["label"]
)

print("\nDataset split:")
print("Train:", len(train_df))
print("Validation:", len(val_df))
print("Test:", len(test_df))

# 5. CONVERT TO HUGGING FACE DATASETS
train_dataset = Dataset.from_pandas(
    train_df[["text", "label"]],
    preserve_index=False
)

val_dataset = Dataset.from_pandas(
    val_df[["text", "label"]],
    preserve_index=False
)

test_dataset = Dataset.from_pandas(
    test_df[["text", "label"]],
    preserve_index=False
)

print("\nHugging Face datasets created.")

# 6. LOAD DISTILBERT TOKENIZER
model_name = "distilbert-base-uncased"

tokenizer = AutoTokenizer.from_pretrained(model_name)

print("Tokenizer loaded!")

# 7. TOKENIZATION
def tokenize_function(examples):

    return tokenizer(
        examples["text"],
        truncation=True,
        padding="max_length",
        max_length=256
    )


train_dataset = train_dataset.map(
    tokenize_function,
    batched=True
)

val_dataset = val_dataset.map(
    tokenize_function,
    batched=True
)

test_dataset = test_dataset.map(
    tokenize_function,
    batched=True
)

print("Tokenization complete!")

# 8. LOAD PRETRAINED DISTILBERT
model = AutoModelForSequenceClassification.from_pretrained(
    model_name,
    num_labels=2
)

print("DistilBERT model loaded!")

# 9. EVALUATION METRICS
def compute_metrics(eval_pred):

    logits, labels = eval_pred

    predictions = np.argmax(logits,axis=-1)

    precision, recall, f1, _ = (
        precision_recall_fscore_support(
            labels,
            predictions,
            average="binary",
            zero_division=0
        )
    )

    accuracy = accuracy_score(labels, predictions)

    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1
    }

# 10. TRAINING CONFIGURATION
training_args = TrainingArguments(
    output_dir="./model/phishing_distilbert",
    eval_strategy="epoch",
    save_strategy="epoch",
    learning_rate=2e-5,

    # Smaller batch size is safer for CPU/RAM
    per_device_train_batch_size=4,
    per_device_eval_batch_size=4,

    # Use 1 epoch for the first CPU test
    num_train_epochs=1,
    weight_decay=0.01,
    load_best_model_at_end=True,
    metric_for_best_model="f1",
    logging_steps=50,
    report_to="none"
)

# 11. CREATE TRAINER
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    eval_dataset=val_dataset,
    processing_class=tokenizer,
    compute_metrics=compute_metrics
)

# 12. START TRAINING
print("\n===== Starting DecisionIQ Phishing Training =====")
trainer.train()

# 13. EVALUATE ON TEST DATA
print("\n===== Evaluating Model =====")

results = trainer.evaluate(test_dataset)

print("\nTest Results:")

for key, value in results.items():

    if isinstance(value, float):
        print(f"{key}: {value:.4f}")

    else:
        print(f"{key}: {value}")

# 14. SAVE MODEL
print("\nSaving model...")

trainer.save_model("./model/phishing_distilbert")

tokenizer.save_pretrained("./model/phishing_distilbert")

print("Training completed successfully!")
print("Model saved to: ./model/phishing_distilbert")