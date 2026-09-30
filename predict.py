import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification


MODEL_PATH = "./model/phishing_distilbert"

tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)

model = AutoModelForSequenceClassification.from_pretrained(MODEL_PATH)

model.eval()


def detect_phishing(text):

    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        padding=True,
        max_length=256
    )

    with torch.no_grad():

        outputs = model(**inputs)

        probabilities = torch.softmax(
            outputs.logits,
            dim=-1
        )

    phishing_probability = probabilities[0][1].item()

    is_phishing = phishing_probability >= 0.5

    confidence = (
        phishing_probability
        if is_phishing
        else 1 - phishing_probability
    )

    risk_score = round(
        phishing_probability * 100
    )

    return {
        "is_phishing": is_phishing,
        "confidence": round(confidence, 2),
        "risk_score": risk_score
    }


if __name__ == "__main__":

    message = input("Enter email/text: ")

    result = detect_phishing(message)

    print("\nDecisionIQ Phishing Detection")
    print("--------------------------------")

    print("Input:", message)
    print("Is Phishing:", result["is_phishing"])
    print("Confidence:", result["confidence"])
    print("Risk Score:", result["risk_score"])