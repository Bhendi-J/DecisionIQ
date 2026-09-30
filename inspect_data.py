import pandas as pd
import numpy as np

def inspect_dataset(name, path, is_excel=False):
    print(f"\n{'='*50}")
    print(f"Inspecting Dataset: {name}")
    print(f"{'='*50}")
    
    try:
        if is_excel:
            df = pd.read_excel(path)
        else:
            df = pd.read_csv(path)
            
        print(f"Row count: {len(df)}")
        print(f"Column names: {list(df.columns)}")
        print("\nData Types:")
        print(df.dtypes)
        print("\nMissing values:")
        print(df.isnull().sum())
        print(f"\nDuplicate rows: {df.duplicated().sum()}")
        
        # Date range if applicable
        date_cols = [col for col in df.columns if 'date' in col.lower() or 'time' in col.lower()]
        for col in date_cols:
            try:
                df[col] = pd.to_datetime(df[col])
                print(f"\nDate range for {col}: {df[col].min()} to {df[col].max()}")
            except:
                pass
                
        # Unique sectors (for cashflow data)
        if 'sector' in df.columns:
            print(f"\nUnique sectors: {df['sector'].unique()}")
            
        # Target distribution (for cashflow data)
        target = 'cashflow_stress_next_month'
        if target in df.columns:
            print(f"\nTarget distribution ({target}):")
            print(df[target].value_counts(normalize=True))
            
        print("\nBasic Statistics:")
        print(df.describe())
        
    except Exception as e:
        print(f"Error loading/inspecting data: {e}")

if __name__ == '__main__':
    retail_path = r"c:\Users\Prathamesh\OneDrive\Desktop\DecisionIQ\Datasets\online+retail\Online Retail.xlsx"
    cashflow_path = r"c:\Users\Prathamesh\OneDrive\Desktop\DecisionIQ\Datasets\archive\small_business_cashflow.csv"
    
    inspect_dataset("Online Retail", retail_path, is_excel=True)
    inspect_dataset("Small Business Cashflow", cashflow_path, is_excel=False)
