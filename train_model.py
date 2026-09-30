import joblib
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import classification_report, confusion_matrix

from predict import FEATURES, MODEL_PATH, to_anomaly_score

# ---------- Load data ----------
df = pd.read_csv("data/login_data.csv")

# Only the 5 feature columns go to the model. The label is NOT used for training.
X = df[FEATURES]

# ---------- Train ----------
model = IsolationForest(
    n_estimators=200,
    contamination=0.05,
    random_state=42,
)
model.fit(X)

# ---------- Save the model ----------
joblib.dump(model, MODEL_PATH)
print("Saved model to", MODEL_PATH)

# ---------- Predict on all 1,000 logins ----------
df["prediction"] = model.predict(X)                  # 1 = normal, -1 = anomaly
df["is_anomaly"] = df["prediction"] == -1
df["raw_decision"] = model.decision_function(X)
df["anomaly_score"] = to_anomaly_score(df["raw_decision"]).round(3)
df["risk_score"] = (df["anomaly_score"] * 100).round().astype(int)

# ---------- Save results ----------
df.to_csv("outputs/anomaly_results.csv", index=False)
print("Saved outputs/anomaly_results.csv")

# ---------- Evaluate (labels used ONLY here, for testing) ----------
y_true = df["label"]
y_pred = df["is_anomaly"].astype(int)

print("\nFlagged as anomaly:", int(df["is_anomaly"].sum()), "of", len(df))
print("\nConfusion matrix (rows = actual, columns = predicted):")
print("              pred normal   pred anomaly")
cm = confusion_matrix(y_true, y_pred)
print("actual normal   ", cm[0][0], "          ", cm[0][1])
print("actual anomaly  ", cm[1][0], "          ", cm[1][1])

print("\nClassification report:")
print(classification_report(y_true, y_pred, target_names=["normal", "anomaly"]))