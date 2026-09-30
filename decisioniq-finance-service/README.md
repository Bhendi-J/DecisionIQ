# DecisionIQ — Finance Service Microservice

The **Finance Service** is a core ML microservice of **DecisionIQ**, an AI-powered business intelligence dashboard for SMEs.

It is responsible for:
1. **Prophet Revenue Forecasting**: 90-day time-series forecasting using retail transaction data as a sales/cash-inflow proxy.
2. **XGBoost Cash-Flow Stress Classification**: Supervised ML predicting next month's SME cash-flow stress probability (`cashflow_stress_next_month`).
3. **SHAP Explanations**: Mathematical feature attribution identifying top contributors driving financial risk.
4. **Risk Aggregation Engine**: Fault-tolerant composite scoring combining Finance Risk and Security Risk.
5. **What-If Simulation Engine**: Pure in-memory financial recomputation testing hypothetical business scenario changes without mutating storage.

---

## 1. Project Architecture & Control Flow

```text
React Frontend
      ↓
API Gateway
      ↓
Finance Service (FastAPI :8001)
      ↓
 ┌───────────────┬───────────────────┐
 ↓               ↓                   ↓
Prophet       XGBoost              SHAP
(Forecast)   (Cash-Stress Risk)  (Explanations)
                 ↓
         Risk Aggregation
                 ↓
     Composite Business Health
```

---

## 2. Dataset Strategy & Data Leakage Prevention

| Model | Primary Dataset | Proxy / Target | Data Leakage Controls |
| :--- | :--- | :--- | :--- |
| **Prophet** | `Datasets/online+retail/Online Retail.xlsx` | `Revenue = Quantity × UnitPrice` aggregated daily (Retail sales proxy) | Chronological time-series splitting (no random shuffling). |
| **XGBoost** | `Datasets/archive/small_business_cashflow.csv` (Prototype/Synthetic Dataset) | Target: `cashflow_stress_next_month` (Supervised Target) | Features represent Month N financials predicting Month N+1 risk. `record_id` excluded. |

---

## 3. Features & Business Logic

### Primary Features
- `employees`: Company headcount
- `revenue_usd`: Monthly revenue in USD
- `opex_usd`: Operating expenditure in USD
- `accounts_receivable_days`: Average collection cycle
- `inventory_days`: Average inventory holding cycle
- `loan_balance_usd`: Outstanding debt balance
- `owner_injections_usd`: Owner capital injections
- `sector`: One-hot encoded categorical variable (`Retail`, `Services`, `Manufacturing`, `Healthcare`, `Logistics`, `Hospitality`)

### Engineered Features
1. `profit` = `revenue_usd - opex_usd` (Operating profitability proxy)
2. `expense_ratio` = `opex_usd / (revenue_usd + 1e-5)` (Operational burn rate)
3. `debt_to_revenue_ratio` = `loan_balance_usd / (revenue_usd + 1e-5)` (Leverage burden)
4. `injection_reliance` = `owner_injections_usd / (revenue_usd + 1e-5)` (External capital dependence)
5. `cash_cycle_risk` = `accounts_receivable_days + inventory_days` (Working capital conversion cycle length)

---

## 4. Installation & Quickstart

### Step 1: Install Dependencies
```bash
cd decisioniq-finance-service
pip install -r requirements.txt
```

### Step 2: Offline Model Training
Run offline training scripts to generate model binaries:
```bash
# Train Prophet 90-Day Forecaster
python scripts/train_prophet.py

# Train XGBoost Cash-Flow Risk Classifier
python scripts/train_xgboost.py
```

Model binaries will be saved to:
- `models/prophet/prophet_model.pkl`
- `models/xgboost/xgboost_risk.pkl`

### Step 3: Run FastAPI Microservice
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

---

## 5. API Endpoints & Testing

The service exposes interactive Swagger docs at `http://localhost:8001/docs`.

### 1. Health Check
`GET /health`
```json
{
  "status": "healthy",
  "service": "decisioniq-finance-service",
  "version": "1.0.0"
}
```

### 2. Financial Summary
`GET /finance/summary?security_score=0.40`

### 3. Risk Prediction
`POST /finance/predict`
```json
{
  "sector": "Retail",
  "employees": 12,
  "revenue_usd": 45000,
  "opex_usd": 38000,
  "accounts_receivable_days": 55,
  "inventory_days": 30,
  "loan_balance_usd": 25000,
  "owner_injections_usd": 2000
}
```

### 4. What-If Simulation
`POST /finance/simulate?security_score=0.40`
```json
{
  "expenses_change_pct": 15.0,
  "revenue_change_pct": -10.0,
  "receivable_days_change": 10.0,
  "loan_balance_change_pct": 0.0
}
```

---

## 6. Evaluation Strategy & Metrics

- **Prophet Forecaster**: Evaluated on unseen 90-day historical window. Metrics tracked: MAE, RMSE, MAPE.
- **XGBoost Classifier**: Evaluated on unseen 20% chronological test split. Class imbalance (~83% no-stress vs 17% stress) handled via `scale_pos_weight`. Metrics tracked: Precision, Recall, F1-Score, ROC-AUC, Confusion Matrix.

---

## 7. Known Limitations
- The Online Retail dataset represents transaction sales, acting as a proxy for revenue / cash inflow. It does not contain actual SME cash outflow line items.
- The What-If simulation recomputes financial risk in-memory and does not alter long-term historical records.
