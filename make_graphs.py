import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

df = pd.read_csv("outputs/anomaly_results.csv")
GREEN, RED = "#4c9a6a", "#d1495b"

# Graph 1: Normal vs Anomalous (model predictions)
counts = [(~df["is_anomaly"]).sum(), df["is_anomaly"].sum()]
plt.figure(figsize=(6, 4))
bars = plt.bar(["Normal", "Anomaly"], counts, color=[GREEN, RED])
plt.bar_label(bars)
plt.title("Normal vs Anomalous Logins (Model Predictions)")
plt.ylabel("Number of logins")
plt.tight_layout()
plt.savefig("outputs/normal_vs_anomaly.png", dpi=150)
plt.close()

# Graph 2: Anomaly score distribution
plt.figure(figsize=(7, 4))
plt.hist(df[df.label == 0]["anomaly_score"], bins=30, alpha=0.7,
         color=GREEN, label="Normal logins")
plt.hist(df[df.label == 1]["anomaly_score"], bins=30, alpha=0.7,
         color=RED, label="Injected anomalies")
plt.axvline(0.5, color="black", linestyle="--", label="Decision boundary (0.5)")
plt.xlabel("Anomaly score (0 to 1)")
plt.ylabel("Number of logins")
plt.title("Anomaly Score Distribution")
plt.legend()
plt.tight_layout()
plt.savefig("outputs/anomaly_distribution.png", dpi=150)
plt.close()

# Graph 3: Login hour vs failed attempts
rng = np.random.default_rng(1)
plt.figure(figsize=(7, 4.5))
for flag, color, name in [(False, GREEN, "Normal"), (True, RED, "Anomaly")]:
    s = df[df.is_anomaly == flag]
    plt.scatter(s.login_hour + rng.uniform(-0.3, 0.3, len(s)),
                s.failed_attempts + rng.uniform(-0.15, 0.15, len(s)),
                c=color, alpha=0.6, s=25, label=name)
plt.xlabel("Login hour")
plt.ylabel("Failed attempts")
plt.title("Login Hour vs Failed Attempts")
plt.legend()
plt.tight_layout()
plt.savefig("outputs/feature_analysis.png", dpi=150)
plt.close()

print("Saved 3 graphs to outputs/")