import os
import sys
import pandas as pd

# Add root service directory to sys.path
SERVICE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SERVICE_DIR not in sys.path:
    sys.path.insert(0, SERVICE_DIR)

from app.models.xgboost_risk import XGBoostRiskModel

def train():
    print("=== Training XGBoost Cash-Flow Stress Risk Model ===")
    
    BASE_DIR = os.path.dirname(SERVICE_DIR)
    csv_path = os.path.join(BASE_DIR, 'Datasets', 'archive', 'small_business_cashflow.csv')
    if not os.path.exists(csv_path):
        print(f"Error: File not found at {csv_path}")
        return
        
    print(f"Loading small business cashflow dataset from {csv_path}...")
    df = pd.read_csv(csv_path)
    print(f"Raw Data shape: {df.shape}")
    
    risk_model = XGBoostRiskModel()
    print("Engineering features & fitting XGBoost model with chronological split...")
    metrics, trained_xgb = risk_model.train_and_evaluate(df)
    
    print("\n--- XGBOOST EVALUATION METRICS (20% Unseen Test Set) ---")
    for k, v in metrics.items():
        print(f"  {k}: {v}")
        
    model_save_path = os.path.join(SERVICE_DIR, 'models', 'xgboost', 'xgboost_risk.pkl')
    risk_model.save(model_save_path)
    print(f"\nTrained XGBoost model saved to: {model_save_path}")

if __name__ == '__main__':
    train()
