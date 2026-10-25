# DecisionIQ

One FastAPI application integrating the team's finance, login anomaly, and email phishing services. The original service branch histories are preserved in the integration merge.

## Run locally

Requires Python 3.11 or 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --locked
cp .env.example .env
uv run uvicorn decisioniq.main:app --env-file .env --reload --port 8000
```

Open **http://localhost:8000/docs** for the interactive API. Finance and anomaly models are included. Phishing requires the separate trained artifact described below; its absence does not prevent the other services from starting.

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/health` | Process health and readiness of every model; may report `degraded` |
| GET | `/ready` | Returns 200 only when all three models load; otherwise 503 |
| POST | `/assess` | Supplied company financials plus optional login/email analysis and combined risk |
| POST | `/finance/predict` | Cash-flow stress probability and exact TreeSHAP contributors |
| GET / POST | `/finance/summary` | Forecast, finance risk, SHAP, and optional security score |
| GET | `/finance/forecast?horizon_days=90` | Historical revenue plus 7–180 future days |
| GET / POST | `/finance/unified` | Finance summary with rule-based early warnings |
| POST | `/finance/simulate` | Recompute a supplied baseline under what-if changes |
| POST | `/anomaly/score` | Score a login with the original Isolation Forest model |
| POST | `/phishing/predict` | Classify email text with the supplied DistilBERT model |
| GET | `/finance/health`, `/anomaly/health`, `/phishing/health` | Service-specific model readiness; 503 when unavailable |

GET finance summaries use the original default SME profile. POST variants score the supplied financial profile. **The revenue forecast always uses the bundled demonstration retail history**, not the submitted company's monthly financials. Its forecast starts after December 9, 2011, the final observation in that dataset.

### Combined assessment

```bash
curl http://localhost:8000/assess \
  -H 'Content-Type: application/json' \
  -d '{
    "finance": {
      "sector": "Retail",
      "employees": 12,
      "revenue_usd": 50000,
      "opex_usd": 42000,
      "accounts_receivable_days": 45,
      "inventory_days": 30,
      "loan_balance_usd": 20000,
      "owner_injections_usd": 2000
    },
    "login": {
      "login_hour": 3,
      "failed_attempts": 8,
      "new_device": 1,
      "login_frequency": 1,
      "location_difference": 1
    },
    "email": {"text": "Please review the attached invoice"}
  }'
```

Each security signal reports `available`, `unavailable`, or `not_requested`. `security_coverage` is `complete` when all requested security checks succeeded, `partial` when only some succeeded, or `none` when no security score is available. A partial result is provisional and must be displayed with its coverage.

All combined scores use **0–1, higher means greater risk**:

```text
security_score = max(available anomaly_score, available phishing_probability)
composite_score = 0.7 * finance_probability + 0.3 * security_score
```

This is an explicit aggregation policy, not a calibrated probability of overall business failure. It retains finance's original 70/30 weighting. The anomaly score is the original sigmoid transform of Isolation Forest's decision function. Security endpoints also retain their original integer `risk_score` on 0–100 for display. Phishing `confidence` measures confidence in the selected class; aggregation uses `phishing_probability` instead.

When no security score is available, `security_score` is `null` and the composite equals the finance score. No mock security baseline is inserted. Direct finance summary/simulation calls may accept an already computed `?security_score=0.6`; values outside 0–1 are rejected.

### What-if

```bash
curl http://localhost:8000/finance/simulate \
  -H 'Content-Type: application/json' \
  -d '{"base_input":{"revenue_usd":50000,"opex_usd":35000},"expenses_change_pct":15,"revenue_change_pct":-10}'
```

The simulation recomputes both baseline and scenario from the supplied financial profile without changing saved data or rerunning security models.

## Phishing model setup

The `email_phishing_detection` branch excludes `model/` in its gitignore and supplies no trained weights or tokenizer. Obtain Jiya's **complete saved model directory**, including the configuration, model weights, and tokenizer files, and place it at:

```text
services/phishing/models/phishing_distilbert/
```

Alternatively set `PHISHING_MODEL_PATH` to a local model directory. Install the extra and restart:

```bash
uv sync --locked --extra phishing
uv run --extra phishing uvicorn decisioniq.main:app --env-file .env --port 8000
```

Inference loads local files only and never downloads a substitute model. The expected labels are **0=legitimate, 1=phishing**. The original 256-token limit is retained; responses report `truncated: true` for longer inputs. Until a trained artifact is supplied, `/phishing/predict` returns 503 and `/assess` explicitly marks that signal unavailable.

To train using the original cleaned CEAS08 CSV (obtain it from the source branch or your dataset storage):

```bash
uv sync --locked --extra phishing --extra training
uv run --extra phishing --extra training python -m services.phishing.train \
  --data data/CEAS08_DecisionIQ_clean.csv --sample-size 10000 --epochs 1
```

Remove `--sample-size` to use the full dataset. Training requires downloading the base DistilBERT checkpoint; API startup and inference do not. Model directories remain ignored by Git so large trained weights can be distributed separately.

## Layout and cleanup

```text
decisioniq/                 Shared FastAPI app, configuration, assessment orchestration
services/finance/           Forecasting, cash-flow risk, SHAP, early warnings, what-if
services/anomaly/           Login model, API, inference, training entrypoint
services/phishing/          Email API, inference, training entrypoint
tests/                     API contracts, real finance/anomaly inference, failure handling
pyproject.toml + uv.lock    Shared dependencies, optional ML extras, reproducible versions
```

Excluded from the integrated tree: raw training/benchmark datasets, bytecode and caches, editor settings, duplicate model copies, generated charts/results, ad hoc investigation scripts, standalone demo dashboards, and unused bankruptcy benchmark models. All inference code, active supplied model artifacts, and reproducible training entrypoints are retained. The ~7 KB daily revenue CSV replaces the ~24 MB runtime workbook and is derived using finance's original cleaning and aggregation rules. Cleanup changes the current tree; it does not rewrite Git history or delete contributor branches.

Finance artifacts were converted from pickle to Prophet/XGBoost JSON, with matching predictions checked before and after conversion. The anomaly artifact retains its original joblib format and matching scikit-learn version.

Source branches and integration inputs:

| Service | Branch | Source commit |
| --- | --- | --- |
| Finance | `Finance-model-branch` | `a64ec1b23dc3211ee4029a7f02fd00db508da61c` |
| Login anomaly | `security-anomaly` | `367efb8fefd16b76cf47787a322e0d1cd3c53bbc` |
| Email phishing | `email_phishing_detection` | `e8f8acd131b7b4454cf0b78b9972146758517d89` |

## Retrain finance or anomaly models

Run from the repository root and restart the API after changing model artifacts:

```bash
uv run python -m services.finance.scripts.train_prophet
uv run python -m services.finance.scripts.train_xgboost --data data/small_business_cashflow.csv
uv run python -m services.anomaly.train_model --data data/login_data.csv
```

For a raw Online Retail workbook, add `--data data/OnlineRetail.xlsx` to the Prophet command and enable `--extra training`. Keep raw datasets under the ignored root `data/` directory. Finance's classification data and anomaly's original login data are prototypes/synthetic datasets; integration tests verify software behavior, not model suitability for production decisions.

## Verify

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

To include the real local Transformers adapter test, run `uv run --extra phishing pytest -q`. It creates a tiny untrained model in a temporary directory to test loading, probabilities, and truncation; this fixture is never shipped as the phishing model.

## Docker

```bash
docker build -t decisioniq .
docker run --rm -p 8000:8000 decisioniq
```

Include phishing dependencies with `--build-arg INSTALL_PHISHING=true`, then mount your trained artifact:

```bash
docker run --rm -p 8000:8000 \
  -v /absolute/path/phishing_distilbert:/models/phishing:ro \
  -e PHISHING_MODEL_PATH=/models/phishing decisioniq
```

The container health check measures process liveness. Use `/ready` when your deployment requires every model, including phishing, to be available. Browser origins can be configured with `CORS_ORIGINS` as a comma-separated list.
