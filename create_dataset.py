import numpy as np
import pandas as pd

# Fixed seed so you get the exact same data every time you run this
rng = np.random.default_rng(42)

N_NORMAL = 950
N_ANOMALY = 50

# ---------- Normal logins ----------
normal = pd.DataFrame({
    # mostly working hours, centered around 1 PM, kept between 8 and 19
    "login_hour": np.clip(rng.normal(13, 3, N_NORMAL).round(), 8, 19).astype(int),
    # mostly 0 or 1 failed attempts, never more than 2
    "failed_attempts": np.clip(rng.poisson(0.5, N_NORMAL), 0, 2),
    # rarely a new device (3% of the time)
    "new_device": (rng.random(N_NORMAL) < 0.03).astype(int),
    # around 5 logins per day, kept between 2 and 9
    "login_frequency": np.clip(rng.normal(5, 1.5, N_NORMAL).round(), 2, 9).astype(int),
    # rarely an unusual location (2% of the time)
    "location_difference": (rng.random(N_NORMAL) < 0.02).astype(int),
    "label": 0,   # 0 = normal (used ONLY for testing, never for training)
})

# ---------- Suspicious logins ----------
anomaly = pd.DataFrame({
    # odd hours: late night or early morning
    "login_hour": rng.choice([0, 1, 2, 3, 4, 5, 23], N_ANOMALY),
    # many failed attempts
    "failed_attempts": rng.integers(5, 11, N_ANOMALY),
    # usually a new device (90%)
    "new_device": (rng.random(N_ANOMALY) < 0.9).astype(int),
    # low login frequency
    "login_frequency": rng.integers(1, 3, N_ANOMALY),
    # usually an unusual location (90%)
    "location_difference": (rng.random(N_ANOMALY) < 0.9).astype(int),
    "label": 1,   # 1 = injected anomaly (used ONLY for testing)
})

# ---------- Combine, shuffle, save ----------
df = pd.concat([normal, anomaly])
df = df.sample(frac=1, random_state=42).reset_index(drop=True)
df.to_csv("data/login_data.csv", index=False)

print("Saved data/login_data.csv")
print("Shape:", df.shape)
print("Label counts:", df["label"].value_counts().to_dict())