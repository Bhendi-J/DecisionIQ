# ForeSight

React dashboard and FastAPI backend for company sales analysis, login anomaly detection, and email phishing analysis.

## Run locally

Requires Python 3.11/3.12, Node.js 22+, and `uv`.

```bash
./scripts/run_local.sh
```

Open http://127.0.0.1:8082 and create an account. The launcher installs dependencies, builds the frontend, and installs the pinned phishing model and optional public demo data **locally**. These downloaded files and runtime company records are excluded from Git.

To start without public samples:

```bash
INSTALL_DEMO_DATA=0 ./scripts/run_local.sh
```

To disable the optional phishing dependencies/model setup, also set `INSTALL_PHISHING=0`. Set `DECISIONIQ_PORT` to use a different port.

## Accounts and access

Registration creates a private company with the creator as owner. Owners manage company settings, API credentials, and team membership. Members can upload and analyze company data. Only administrators can browse all companies and use Model Lab.

Add existing registered users through **Manage team**. No invitation emails are sent. Provision an administrator through trusted local access:

```bash
uv run python -m scripts.create_admin --email your-email --promote
```

There are no default accounts or passwords. Passwords are hashed; sessions expire and are revoked server-side on logout. Email verification, password recovery, and MFA are not implemented.

## Data and configuration

Reports, datasets, evaluation output, databases, and uploads must remain local and ignored by Git. Repository manifests contain download paths and integrity hashes, not observation records. The optional public sales samples adapt Daqing Chen’s [Online Retail](https://doi.org/10.24432/C5BW33) (UCI, 2015), licensed CC BY 4.0; they retain GBP and historical dates. They represent selected recorded sales, not cash availability or complete company revenue.

To retrieve the optional demo CSVs separately:

```bash
uv run python -m scripts.install_demo_data
```

You can also generate the compact sample locally with `scripts.prepare_demo_data --input /path/to/OnlineRetail.xlsx`. Missing sample CSVs do not prevent registration or use of private upload workspaces. Existing stored company records are preserved.

Use `.env.example` for path and origin settings. Internal `decisioniq` module names and `DECISIONIQ_*` settings remain for compatibility. Database default: ignored `data/dashboard.sqlite3`. `FORESIGHT_DEMO_SALES_PATH` can select an optional local sample CSV. External LLM processing is disabled.

For a custom trained email classifier, export model/configuration/tokenizer files and set `PHISHING_MODEL_PATH` to that local directory. Default installation uses the pinned contributor export and verifies its size/hash before activation. Prediction loads local files only, analyzes up to 256 tokens, and stores results/text length instead of raw email contents. A negative model result does not guarantee safety.

## API

The frontend uses the same-origin `/api` endpoints. Account routes are under `/api/auth`; cookie-authenticated writes require the session's `X-CSRF-Token`, handled automatically by the UI. Company applications send `X-API-Key` to `/api/intake/sales` and `/api/intake/logins`. Obtain credentials from an owner in Data Hub; rotation revokes the previous credential. Paused intake rejects API submissions while manual uploads remain available.

Sales uploads support CSV/XLSX. Review mappings, date/number conventions, native currency, and validation errors before processing. API records require stable IDs; exact retries are deduplicated and conflicting values are rejected. No automatic currency conversion is applied.

Use HTTPS and secure cookies for deployment, and configure `FORESIGHT_ORIGIN` behind a proxy if needed. Runtime data is not application-encrypted. Retention, backups, durable job/restart recovery, and production operations remain to be implemented.

## Checks

Prepare ignored demo assets for the existing sample-workspace tests:

```bash
uv run python -m scripts.install_demo_data
uv run --extra phishing pytest -q
npm --prefix frontend run build
```

Opt into real trained-artifact checks with `PHISHING_RUN_ARTIFACT_TESTS=1` after installing the model. Browser tests need a running backend on port 8083 and the same separate `DECISIONIQ_DB_PATH` exported to the test process. Run `npm --prefix frontend run test:browser`. Tests generate disposable accounts in that separate database.

## Docker

Build with `docker build -t foresight .`. Start with `docker run --rm -p 8000:8000 -v foresight-data:/app/data foresight`. Add `--build-arg INSTALL_PHISHING=true` for email-model dependencies and mount the trained export read-only, setting `PHISHING_MODEL_PATH`. Public sample data is optional; the image can start with empty private workspaces.
