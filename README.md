# ForeSight

A local, company-focused business intelligence dashboard for a college demonstration. React presents sales outlooks, product performance, independent security signals, data ingestion, and reporting reminders. FastAPI integrates the team's finance, login anomaly, and phishing services.

The interface uses graphite surfaces, warm ivory and brass accents, locally bundled **Manrope** and **Geist Mono** variable fonts, interactive SVG charts, and responsive layouts. There are no external font, analytics, or LLM requests.

## Run the dashboard

Requires Python 3.11 or 3.12, Node.js 22+, and [uv](https://docs.astral.sh/uv/).

```bash
./scripts/run_local.sh
```

Open **http://127.0.0.1:8082**. The script installs locked dependencies, builds the dashboard, and runs the local backend. For a different port, use `DECISIONIQ_PORT=8084 ./scripts/run_local.sh`.

Or run the steps separately:

```bash
uv sync --locked
npm --prefix frontend ci
npm --prefix frontend run build
uv run uvicorn decisioniq.main:app --host 127.0.0.1 --port 8082
```

For frontend development, keep FastAPI on port 8082 and run `npm --prefix frontend run dev` in a second terminal. Vite serves port 5173 and proxies API requests. Rebuild the frontend to update the version served directly by FastAPI.

Internal Python module names and existing `DECISIONIQ_*` environment variables are retained for compatibility. Optional environment overrides are documented in `.env.example`. To load a copied `.env`, add `--env-file .env` to the uvicorn command. Runtime data defaults to the ignored `data/dashboard.sqlite3` file.

## Workspace experience

- **Overview:** recorded sales, an evaluated outlook, units where known, product contribution, and independent operational signals.
- **Data Hub:** CSV/XLSX uploads, field mapping, date and number conventions, validation, processing history, API credential rotation, and intake controls.
- **Sales Outlook:** actual and forecast observations, indicative ranges, held-out error, stronger/weaker weeks only when supported, product analysis, and explicit volume/price scenarios.
- **Security:** real Isolation Forest inference, company API login events, clearly labeled synthetic samples, and phishing readiness.
- **Insights:** downloadable, deterministic evidence summaries. External GenAI is not configured or represented as active.
- **Activity:** reporting schedules, persisted notifications, snooze, and processing/configuration history.
- **Model Lab:** the original prototype cash-stress classifier and native TreeSHAP, separated from company-facing sales conclusions.

The sidebar switcher is labeled **Demo / admin**. Aster Trading, Maison Supply, and Nordhaus are fictional sample workspaces representing different customer-country segments of a single public UCI retailer. They are not independent observed businesses. Create an upload workspace to analyze a different source; public samples are read-only.

## Financial meaning and provenance

The dashboard's compact public dataset contains twelve selected merchandise SKUs per country segment. It retains signed quantities, including cancellations/returns, and excludes postage/manual adjustment codes. Its target is **net recorded sales value**, not received cash, profit, or complete retailer revenue. Amounts remain in **GBP**, and forecasts start after the actual historical cutoff in 2011. See [dataset provenance](services/finance/data/PROVENANCE.md) for the source, CC BY 4.0 attribution, transformations, and reproduction command.

Forecasting needs at least 84 calendar days under this demonstration's eligibility policy. Missing calendar days are treated as unknown unless the upload explicitly declares them to mean zero sales. The last 28 days are withheld; Prophet provides the outlook only when its MAE beats a weekly seasonal baseline. The selected method is shown. Longer outlooks extrapolate beyond the evaluation window; ranges are indicative rather than performance guarantees. If complete forecast weeks have essentially the same expected total, the interface does not invent a strongest/quietest week.

Product ranking uses a fixed subset selected from the complete public history; the backtest evaluates the resulting series, not the product-selection process. Source periods, currencies, and sample labels remain visible. Units stay unavailable when source quantities are incomplete. No missing uploaded financial fields are replaced with the legacy model's default SME values.

The legacy `/finance/*` endpoints retain the separate original positive-sales aggregate and synthetic/prototype XGBoost experiment. They are available for compatibility and Model Lab exploration, not a validated probability of financial trouble for an uploaded company.

## Upload and API ingestion

Both paths use the same company-scoped normalization, stable-ID checks, and processing pipeline. Batches are limited to 5 MB / 25,000 rows; uploads accept CSV/XLSX. Invalid rows block processing with location-specific explanations. Choose date order and decimal convention explicitly. There is no automatic foreign-exchange conversion.

1. Create an upload workspace and select its native currency.
2. Upload a file, review the suggested mappings, validate, and process.
3. For integration, activate API intake in the Data Hub and generate a credential.
4. Copy the key once; only its hash is stored. Rotation revokes the prior key.

```bash
curl http://127.0.0.1:8082/api/intake/sales \
  -H "X-API-Key: $FORESIGHT_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"currency":"GBP","records":[{"record_id":"order-001","date":"2026-10-01","product_id":"SKU-1","product":"Notebook","units":3,"sales":150}]}'
```

The accepted response includes `batch_id`. Follow it with the authenticated dashboard's processing history or `GET /api/batches/{batch_id}` using its signed demo session. Exact replayed records are skipped; an existing stable ID with different values is rejected. API records require IDs. Uploads without IDs explain that exact normalized rows are deduplicated; map IDs when identical purchases can occur.

Login-time integration:

```bash
curl http://127.0.0.1:8082/api/intake/logins \
  -H "X-API-Key: $FORESIGHT_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"event_id":"login-001","occurred_at":"2026-10-25T10:30:00Z","login_hour":16,"failed_attempts":0,"new_device":0,"login_frequency":5,"location_difference":0}'
```

API credentials determine the workspace; request fields cannot select another company. Paused or upload-only intake returns `409 intake_paused`; manual uploads remain available. Frontend sessions, batches, events, exports, and stored observations remain company-scoped. Demo workspace switching is deliberately open for review and **is not production authentication**. `DECISIONIQ_DEMO_MODE=0` disables demo session creation; a real identity provider is outside this college demo.

## Reporting reminders

A server worker checks persisted schedules every 30 seconds while the backend runs, including when no browser is open. Cadence defaults to 24 hours and can be changed with the due date and required reporting-period coverage in Activity.

- Paused API + overdue missing data: upload or resume intake.
- Upload-only + overdue missing data: upload the required reporting period.
- Data received but unprocessed: review/process that batch instead of uploading duplicates.
- Active API: no paused-intake upload reminder. Data periods and connection state remain visible.
- Current coverage resolves a reminder. Snooze postpones repeated notifications.

Reminders are in-app only. There is no real email/SMS delivery. Upload time is separate from observed data coverage, so re-uploading an old file does not make an overdue period current.

## Phishing model

The source branch does not contain trained DistilBERT weights/tokenizer. Until the contributor's complete saved directory is supplied, the UI shows setup required and the direct prediction endpoint returns 503. Other services remain usable.

Place the complete artifact under `services/phishing/models/phishing_distilbert/` or set `PHISHING_MODEL_PATH`. Expected labels: 0=legitimate, 1=phishing.

```bash
uv sync --locked --extra phishing
uv run --extra phishing uvicorn decisioniq.main:app --host 127.0.0.1 --port 8082
```

Or use `INSTALL_PHISHING=1 ./scripts/run_local.sh`. Inference loads local files only, retains the original 256-token limit, reports truncation, and bounds native CPU threads via `PHISHING_TORCH_THREADS` (default 1). Successful manual email analysis stores the result and text length, not raw email text.

## Verify

```bash
uv run --extra phishing pytest -q
uv run ruff check .
uv run ruff format --check .
npm --prefix frontend run build
```

The optional phishing adapter test creates a tiny untrained temporary fixture to verify actual Transformers loading/inference; that fixture is never deployed as the phishing model. Core tests also run without the optional extra, with that adapter test skipped.

For browser verification, run a second backend with a separate database:

```bash
DECISIONIQ_DB_PATH=/tmp/decisioniq-browser-qa.sqlite uv run uvicorn decisioniq.main:app --host 127.0.0.1 --port 8083
npm --prefix frontend run test:browser
```

Browser checks use installed Google Chrome. GitHub CI installs it explicitly. Tests cover navigation, fonts, distinct workspaces, the upload-to-forecast workflow, conditional scenarios, real login analysis, search/export, integration controls, reporting schedules, snooze persistence, and mobile layout. Test runtime data and screenshots are ignored.

## Docker

```bash
docker build -t foresight .
docker run --rm -p 8000:8000 -v foresight-data:/app/data foresight
```

The multistage build compiles the React frontend and serves it from FastAPI. Include phishing dependencies with `--build-arg INSTALL_PHISHING=true` and mount the trained model read-only, setting `PHISHING_MODEL_PATH`. `/health` reports process/model health; `/ready` returns 503 until all three trained models are available.

## Repository and original services

```text
frontend/                   React/TypeScript dashboard and bundled font dependencies
decisioniq/                Shared API, assessment orchestration
decisioniq/dashboard/      Local store, sessions, intake, sales analysis, reminders
services/                   Original finance, anomaly, and phishing models/adapters
scripts/                    Local launcher and reproducible public-data preparation
tests/                      API/model checks
frontend/tests/             Real-browser and accessibility workflows
```

Raw training datasets, bytecode/caches, duplicate models, generated charts, editor settings, and unused standalone demos are excluded. Active supplied models, training entrypoints, compact attributed samples, and original branch ancestry are retained. Finance artifacts use portable JSON, with original-versus-converted predictions checked. The anomaly artifact retains the matching scikit-learn version.

Integration inputs: finance `a64ec1b`, anomaly `367efb8`, phishing `e8f8acd`. The implementation lives on `integration/unified-services` in the separate checkout; no GitHub publication has been authorized.
