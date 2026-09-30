# DecisionIQ — Finance Service Microservice

The **Finance Service** is a core ML microservice of **DecisionIQ**, an AI-powered business intelligence dashboard for SMEs.

It provides a **multi-model financial intelligence engine** delivering revenue forecasting, cash-flow stress risk prediction, SHAP explainability, rule-based early warning signals, and real-time What-If scenario simulations.

---

## 1. Project Architecture & Capability Stack

```text
               React Frontend / Dashboard
                           │
                      API Gateway
                           │
             Finance Service (FastAPI :8001)
                           │
    ┌──────────────────────┼──────────────────────┐
    ▼                      ▼                      ▼
Forecasting Layer   Classification Layer   Explainability Layer
(Prophet / Ridge)    (XGBoost Risk)         (SHAP Explanations)
    │                      │                      │
    └──────────────────────┼──────────────────────┘
                           ▼
            Rule Engine & Early Warnings
                           ▼
          Unified Endpoint & What-If Engine
```

### Core Services & Components:
1. **Revenue Forecasting Layer**: Time-series revenue/cash-inflow forecasting using Prophet (with fallback to Ridge-Fourier). Evaluated across UCI Online Retail, Walmart, and Rossmann datasets.
2. **Cash-Flow Stress Classifier**: XGBoost model predicting next-month SME distress risk (`cashflow_stress_next_month`). Benchmarked against Taiwanese and Polish Corporate Bankruptcy datasets.
3. **SHAP Explainability Engine**: Calculates directional impact (positive/negative) for top features driving risk probabilities.
4. **Early Warning Rule Engine**: Calculates rule-based financial indicators:
   - Cash Runway (months)
   - Monthly Net Burn Rate
   - Debt Service Coverage Ratio (DSCR)
   - Receivables Aging Risk Index
5. **What-If Simulation Engine**: In-memory scenario simulator (e.g. OPEX +15%, Revenue -10%) that recomputes modified risk without mutating persistent storage.
6. **Unified Service Endpoint (`/finance/unified`)**: Combines forecast, cash-stress risk, SHAP explanations, early warning signals, and composite business health into a single payload.

---

## 2. Directory Structure

```text
decisioniq-finance-service/
├── app/
│   ├── main.py                  # FastAPI application entrypoint & routing
│   ├── models/                  # ML inference wrapper classes (ProphetForecaster, XGBoostRiskModel)
│   ├── schemas/                 # Pydantic request/response data validation models
│   ├── services/                # Early warning engine, SHAP calculator, What-If simulator
│   └── routers/                 # API endpoint routers (/finance/unified, /finance/what-if, etc.)
├── models/                      # Saved trained binary models (.pkl)
│   ├── prophet/
│   │   └── prophet_model.pkl
│   └── xgboost/
│       └── xgboost_risk.pkl
├── scripts/                     # Standalone training scripts
│   ├── train_prophet.py
│   └── train_xgboost.py
├── run_full_eval.py             # Complete multi-model training & evaluation pipeline script
├── requirements.txt             # Service dependencies
└── README.md                    # Project documentation
```

---

## 3. Dataset Strategy & Data Leakage Prevention

| Layer | Primary Dataset | Purpose / Target | Data Leakage Controls |
| :--- | :--- | :--- | :--- |
| **Forecasting** | `UCI Online Retail` | Daily revenue aggregation (`Quantity * UnitPrice`) for 90-day time-series forecasting. | Chronological train/test split (last 90 days held out for evaluation). No random shuffling. |
| **Forecasting Benchmarks** | `Walmart Sales`, `Rossmann Sales` | Benchmark forecasting performance across diverse retail environments. | Chronological evaluation per store/time-series. |
| **Cash-Stress Risk** | `Small Business Cashflow` | SME financial features predicting `cashflow_stress_next_month`. | Features represent Month N financials predicting Month N+1 risk. `record_id` excluded. |
| **Distress Benchmarks** | `Taiwanese Bankruptcy`, `Polish Companies` | External financial distress benchmarks to test XGBoost classification capacity. | Stratified 80/20 train/test split. |

---

## 4. Setup & Installation Guide

### Step 1: Prerequisites
- Python 3.9+ (Python 3.10 to 3.12 recommended)
- Git

### Step 2: Clone & Navigate to Service Directory
```bash
git clone <repository-url>
cd DecisionIQ/decisioniq-finance-service
```

### Step 3: Create & Activate Virtual Environment
**On Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**On macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 4: Install Dependencies
```bash
pip install -r requirements.txt
```

---

## 5. Training & Evaluation Pipeline

### Option A: Run End-to-End Multi-Model Pipeline (Recommended)
To train all forecasting and classification models, generate benchmark evaluation metrics (MAE, RMSE, MAPE, ROC-AUC, F1), run SHAP analysis, and execute What-If tests in one step:

```bash
python run_full_eval.py
```

This updates model artifacts in `models/prophet/prophet_model.pkl` and `models/xgboost/xgboost_risk.pkl`.

### Option B: Run Standalone Training Scripts
```bash
# Train Prophet Forecaster
python scripts/train_prophet.py

# Train XGBoost Cash-Flow Risk Classifier
python scripts/train_xgboost.py
```

---

## 6. Running the FastAPI Server

Start the live microservice on port `8001`:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

Server logs will confirm:
```text
INFO:     Uvicorn running on http://0.0.0.0:8001 (Press CTRL+C to quit)
```

---

## 7. API Endpoints & Usage

Interactive Swagger API documentation is available at:
👉 **`http://localhost:8001/docs`**

### 1. Health Check
`GET /health`
```bash
curl http://localhost:8001/health
```
**Response:**
```json
{
  "status": "healthy",
  "service": "decisioniq-finance-service",
  "version": "1.0.0"
}
```

### 2. Unified Finance Assessment
`POST /finance/unified`

**Sample Request Payload:**
```json
{
  "sector": "Retail",
  "monthly_revenue": 50000.0,
  "monthly_opex": 42000.0,
  "cash_buffer": 15000.0,
  "debt_service": 3000.0,
  "receivables_aging_days": 45.0,
  "revenue_growth_rate": -0.05
}
```

**PowerShell Command:**
```powershell
Invoke-RestMethod -Uri "http://localhost:8001/finance/unified" -Method POST -Headers @{"Content-Type"="application/json"} -Body '{
  "sector": "Retail",
  "monthly_revenue": 50000.0,
  "monthly_opex": 42000.0,
  "cash_buffer": 15000.0,
  "debt_service": 3000.0,
  "receivables_aging_days": 45.0,
  "revenue_growth_rate": -0.05
}'
```

### 3. What-If Simulation
`POST /finance/what-if`

**Sample Request Payload:**
```json
{
  "current_data": {
    "sector": "Retail",
    "monthly_revenue": 50000.0,
    "monthly_opex": 42000.0,
    "cash_buffer": 15000.0,
    "debt_service": 3000.0,
    "receivables_aging_days": 45.0,
    "revenue_growth_rate": -0.05
  },
  "opex_change_pct": 15.0
}
```

---

## 8. Development Guidelines & Best Practices

- **Adding New Features**: When modifying feature schemas, ensure both `app/schemas/finance_schema.py` and `app/models/xgboost_risk.py` feature engineering functions remain synchronized.
- **Model Storage**: Do not commit large uncompressed dataset dumps; commit only trained binary models in `models/` if required.
- **Data Safety**: Always ensure time-series splits remain strictly chronological during forecasting evaluations to prevent data leakage.
