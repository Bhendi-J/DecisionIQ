import os
import sys
import pandas as pd

# Add root service directory to sys.path
SERVICE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SERVICE_DIR not in sys.path:
    sys.path.insert(0, SERVICE_DIR)

from app.models.prophet_forecaster import ProphetForecaster

def train():
    print("=== Training Prophet Forecaster ===")
    
    BASE_DIR = os.path.dirname(SERVICE_DIR)
    excel_path = os.path.join(BASE_DIR, 'Datasets', 'online+retail', 'Online Retail.xlsx')
    if not os.path.exists(excel_path):
        print(f"Error: File not found at {excel_path}")
        return
        
    print(f"Loading raw retail data from {excel_path}...")
    df_raw = pd.read_excel(excel_path)
    
    forecaster = ProphetForecaster()
    print("Preprocessing transaction data...")
    df_daily = forecaster.preprocess_retail_data(df_raw)
    
    print(f"Aggregated Daily Time-Series shape: {df_daily.shape}")
    print(f"Date range: {df_daily['ds'].min()} to {df_daily['ds'].max()}")
    
    print("Fitting Prophet model with chronological train/test split...")
    metrics = forecaster.fit_and_evaluate(df_daily, test_days=90)
    
    print("\n--- PROPHET EVALUATION METRICS (90-Day Test Window) ---")
    for k, v in metrics.items():
        print(f"  {k}: {v}")
        
    model_save_path = os.path.join(SERVICE_DIR, 'models', 'prophet', 'prophet_model.pkl')
    forecaster.save(model_save_path)
    print(f"\nTrained Prophet model saved to: {model_save_path}")

if __name__ == '__main__':
    train()
