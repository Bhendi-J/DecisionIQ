# ForeSight — Integration and Implementation Report

**Prepared:** 27 October 2026
**Purpose:** Explain what was built, why it was built this way, how it works, and its current limits.
**Implementation reviewed:** account access upgrade `f3e4cab`; original dashboard `f28b37c` and service integration `0e157a1`.
**Delivery:** Local college demonstration on `integration/unified-services`.
**Trained phishing artifact:** contributor commit `40043eacb0bc0151d0a295667b993fee0a199957`.
**Product name:** ForeSight; renamed from DecisionIQ after the implementation review.

## 1. Result delivered

ForeSight now has one working React dashboard and one FastAPI application integrating the finance, login-anomaly, and phishing service code. The interface includes sales analysis, uploads, API intake, security analysis, evidence summaries, and reporting reminders.

The implementation was developed in `/private/tmp/decisioniq-integration`. The original local checkout was left untouched. The integration commit preserves the three contributor branch histories. No changes were pushed to GitHub or published as a hosted application.

The result is a functioning demonstration with real backend processing. Account registration, login, logout, and organization roles have now been added. The trained phishing model is now installed and connected. External GenAI, email verification/recovery, and automatic model promotion remain outside the completed functionality.

## 2. What changed and why

| Work completed | Reason for the change |
| --- | --- |
| Combined the three services under one FastAPI application | Give the frontend a consistent API and remove the need to start separate contributor applications. |
| Organized contributor code under `services/` with shared application configuration | Keep model responsibilities separate while making imports, paths, dependencies, and startup predictable. |
| Added a React/TypeScript dashboard | Provide the actual company interface requested, rather than relying on API documentation or separate prototype screens. |
| Built a graphite dark theme with locally bundled Manrope and Geist Mono fonts | Meet the requested premium visual direction and avoid dependence on external font services. |
| Added accounts, company memberships, revocable sessions, and scoped API keys | Restrict company records to authorized users and keep API intake tied to the correct workspace. |
| Made sales outlooks the primary financial feature | Transaction history supports sales analysis more directly than it supports claims about cash availability or business failure. |
| Added shared upload/API normalization and validation | Ensure different company column names converge on consistent meanings before analysis. |
| Added persistent server-side reminders | Support overdue upload-only companies and paused API intake even when the browser is closed. |
| Retained the original cash-stress experiment in Model Lab | Preserve the contributor's model work while explaining its evidence limits. |
| Added readiness states and explicit missing-model responses | Keep available services usable without presenting missing predictions as reassuring results. |
| Removed unnecessary repository material and added reproducible setup | Reduce duplicate artifacts, generated output, caches, and machine-specific files while retaining required models and training entrypoints. |

Finance model artifacts use portable JSON formats; the XGBoost explanation path uses native TreeSHAP. The anomaly model keeps a matching scikit-learn dependency. Locked Python and JavaScript dependencies make the environment reproducible.

## 3. How the system is organized

The browser displays the React application. It sends requests to FastAPI, which checks workspace identity, validates input, calls the appropriate service, and reads or writes SQLite. Forecast results are cached so ordinary dashboard viewing does not train a model on every request.

```text
Authenticated user / membership-scoped company switcher
                    |
           React / TypeScript dashboard
                    |
                 FastAPI
          __________|____________________
         |          |                    |
   Sales intake  Login analysis     Email analysis adapter
   and analysis  Isolation Forest  Local DistilBERT interface
         |          |                    |
         +----------+--------------------+
                    |
        Company-scoped SQLite records
        batches / sales / events / forecasts
        schedules / notifications / activity
                    |
       Server reminder check every 30 seconds
```

The main source areas are `frontend/` for the interface, `decisioniq/dashboard/` for intake and workspace behavior, `services/` for contributor model services, and `tests/` plus `frontend/tests/` for verification.

SQLite was chosen to make the college demo easy to run on one machine. It persists data across normal restarts. It is not a substitute for a production database, durable job queue, backup policy, and deployment design.

## 4. How company data enters the system

### Upload workflow

1. Create an upload workspace and choose its native currency.
2. Upload a CSV or XLSX file, within the 5 MB / 25,000-row limits.
3. Review suggested field mappings and select the file's date and decimal conventions.
4. Validate the mapped records. Errors identify the affected rows and block processing.
5. Process the accepted batch. Sales observations are stored, analysis is refreshed, and processing history records the result.

The supported sales schema includes a transaction date, a sales amount or units multiplied by unit price, optional product identity, optional quantities, and record identity. Currency must match the workspace; there is no automatic currency conversion. Missing quantities remain unavailable. Missing required sales values are rejected.

For example, a company's `sold_on`, `item`, and `amount` columns can map to `date`, `product`, and `sales`. That mapping needs confirmation because a column called `amount` might otherwise mean invoice value, payment received, tax, or another quantity.

### API workflow

A company application can push sales records to `/api/intake/sales` and login events to `/api/intake/logins`. Login events can be sent when a login occurs; sales updates follow the company's reporting schedule. The server does not automatically connect to a company's accounting system merely because the user signs in.

Each credential belongs to one workspace. The credential determines the destination company, and only its hash is stored. Rotation invalidates the previous key. API intake can be activated or paused; paused and upload-only intake rejects API submissions while manual uploads remain possible.

Uploads and API sales batches share the same normalization and processing logic. Stable record IDs make retries safe: an identical record is skipped, while reuse of an ID with changed values is rejected. Without uploaded IDs, exact normalized rows are deduplicated, which can also merge genuinely identical purchases; mapping real transaction IDs avoids that ambiguity.

### Universal schema and GenAI boundary

The implemented solution uses shared domain mappings: sales records, login events, and email analysis have different schemas. The application does not force all company data into one undifferentiated model input. Explicit schema versioning and migration policies remain work for a production intake contract.

Current mapping suggestions use known column aliases and manual confirmation. No external LLM receives uploaded data. A future GenAI component could propose mappings from approved metadata or samples, but validated code should execute the confirmed transformations. This proposal is future work, not an active feature.

No shared LLM has been fine-tuned on company uploads. Removing obvious sensitive fields alone would not establish permission or prevent identification through remaining records. The recommended first GenAI step is restricted mapping assistance and evidence-based explanations after the privacy boundary is agreed, with training considered separately.

Raw sales upload records are retained locally for mapping and processing. The database is not application-encrypted, and automatic retention/deletion rules are not implemented. These facts matter before introducing real company data.

## 5. How sales analysis works

### Evidence used

The demonstration derives compact sales samples from UCI Online Retail. Aster Trading, Maison Supply, and Nordhaus are fictional workspaces assigned to UK, France, and Germany customer-country segments of the same underlying retailer. They are not three independently observed companies.

Each segment retains twelve selected merchandise products. Signed quantities, including returns and cancellations, are retained; nonpositive prices, zero quantities, and non-merchandise codes are excluded. Amounts remain in GBP. The recorded period is 2010–2011, and forecasts start after each series' historical cutoff rather than pretending those observations are current.

The target is net recorded sales for the selected products. Sales records alone do not establish cash received, expenses, profit, available cash, or inventory availability. Public source attribution and transformation details are documented in `services/finance/data/PROVENANCE.md`.

### Forecast process

1. Aggregate the workspace's sales by calendar day.
2. Require at least 84 calendar days under the demo's eligibility rule.
3. Treat omitted dates as unknown unless the company explicitly confirms that missing dates mean zero sales.
4. Hold out the final 28 days for evaluation.
5. Compare Prophet against a weekly seasonal baseline using mean absolute error (MAE).
6. Use Prophet only if its held-out error is lower; otherwise keep the baseline.
7. Store the selected forecast and expose 30-, 60-, or 90-day views with indicative ranges, the analysis cutoff, and evaluation information.

The baseline repeats the last observed week. Prophet can estimate trend and weekly patterns; yearly seasonality is enabled only with sufficient history. The UI identifies stronger and weaker complete weeks only when their expected totals differ meaningfully. A repeating weekly baseline therefore does not invent a unique strongest week.

The public product subset was selected using the full historical dataset. Its backtest evaluates that selected series, not the product-selection process. One 28-day holdout does not establish performance across industries or validate the longer forecast horizons. Model intervals and residual-based baseline bands remain indicative.

### Scenarios and existing finance models

Sales scenarios apply explicit volume and price assumptions to an estimate. They are conditional arithmetic, not learned estimates of customer demand response. Product tables describe observed sales contribution and quantities; separate product-demand models have not been deployed.

The original prototype XGBoost cash-stress model and SHAP contributors remain in Model Lab and compatible legacy endpoints. They are not presented as validated financial-risk probabilities for an uploaded company. No new per-company XGBoost or Random Forest training/deployment loop was implemented. Such models would require suitable target outcomes, representative data, and evaluation first.

## 6. How security analysis works

Login analysis uses the supplied Isolation Forest model. Inputs include login hour, failed attempts, new-device status, login frequency, and location difference. The result includes an anomaly flag and a transformed score. That score is an indicator of unusual model behavior, not a calibrated probability of an attack.

Preloaded login events are explicitly labeled synthetic and remain separate from the public retail transactions. Company API events and manually analyzed inputs carry their own provenance. An anomaly requires review; it does not establish a confirmed breach.

The contributor has now supplied the trained DistilBERT export in commit `40043ea`. Its weight file is 267,832,560 bytes, with a total inference export of 268,545,235 bytes including tokenizer/configuration. ForeSight installs those files from pinned URLs or a verified local Git LFS object and checks every size and SHA-256 before publishing the model directory. The standard launcher enables this model by default. Large weights stay outside ordinary source commits and source ZIPs.

The model loads locally and is connected to authenticated company email analysis. The service preserves a 256-token input limit, reports excluded trailing content, and uses class 1 as phishing according to the contributor's prediction script. This integration uses the supplied weights unchanged and does not retrain them. Missing or unloadable artifacts still produce an explicit unavailable state.

Separate checks verify the real pinned artifact, native logits against API output, health/readiness, and company event storage. The optional adapter test also uses a tiny untrained temporary model to verify loading and inference plumbing. This does not validate phishing accuracy and is never installed as the demonstration's trained model. When real email analysis is enabled, successful dashboard analysis stores the result and text length rather than the raw email text.

Evaluation reconstructed the supplied training script's 2,000-email CEAS08 test split, using the unchanged 34,390-row source CSV. Accuracy was 99.00%, phishing precision 99.49%, recall 98.50%, and F1 98.99%. There were 15 missed phishing emails and 5 false alarms. No normalized exact-text overlap with reconstructed training/validation messages was found. This is one reconstructed random split, with training lineage inferred from the supplied script, not an independent external or temporal benchmark.

A separate short synthetic account-suspension/password-verification lure was not flagged, with a phishing score near 1/100. That observed miss is retained alongside the strong same-source evaluation. The UI labels a negative result **No phishing flag** and states that an unflagged message can still be malicious. Aggregate metrics, versioned artifact details, and reproduction instructions are in `services/phishing/PROVENANCE.md` and `evaluation.json`; raw source emails are not bundled.

Current trained-model integration verification passed 47 backend/model/installer checks on Python 3.11, including the actual pinned weights, native inference versus API output, and readiness with all three services available. All 12 browser workflows passed with the trained phishing model explicitly required, including real email submission and private result storage. The production frontend build and formatting checks also passed.

Finance and security are separate in the company dashboard. The legacy combined assessment endpoint remains available with an explicit aggregation policy and coverage state; its composite index is not a validated probability of company failure.

## 7. How reporting reminders work

The server checks persisted schedules every 30 seconds while the backend runs. Companies configure the due date, required reporting cutoff, and repeat cadence. The default cadence is 24 hours; the interface also supports 24-hour snooze and resume.

| Intake and data state | Behavior |
| --- | --- |
| Active API | Show intake state and data dates; do not issue the paused-intake upload reminder. |
| Paused API, overdue, required data missing | Remind the company to upload or resume intake. |
| Upload-only, overdue, required data missing | Remind the company to upload. |
| Paused/upload-only, overdue, batch awaiting action | Remind the company to review/process the existing batch. |
| Batch currently processing | Suppress the processing reminder while the job runs. |
| Required cutoff covered and no pending batch | Resolve the applicable overdue reminder. |
| Snoozed | Delay repeated notifications until snooze expires. |

Receipt time and sales dates are stored separately, so an old file does not become current merely because it was uploaded again. The current coverage check uses the latest accepted sales date against the required cutoff; it does not prove that every expected transaction was supplied.

Reminders are in-app only. No emails or SMS messages are sent. The scheduler was verified to create a persisted reminder without an open dashboard or follow-up HTTP request. It still requires the backend process to remain running. Sample overdue schedules demonstrate the feature and do not represent an actual company's reporting failure.

## 8. How the interface supports the workflow

| Screen | Main purpose |
| --- | --- |
| Overview | Show recorded sales, evaluated outlook, known units, products, and independent operational signals. |
| Data Hub | Upload, map, validate, process, configure credentials, and control API intake. |
| Sales Outlook | Explore history, forecast ranges, model evaluation, product contribution, and scenarios. |
| Security | Analyze login behavior, inspect event provenance, and show phishing readiness. |
| Insights | Read and download deterministic summaries grounded in available records. |
| Activity | Manage schedules, reminders, snooze, and processing/configuration history. |
| Model Lab | Explore the original experimental finance model with its limitations visible. |

The interface also provides search, notifications, CSV export, responsive navigation, registration, sign-in, sign-out, and owner-controlled team access. Administrators alone can use the all-company switcher and Model Lab; ordinary users can select only companies they belong to. Public sample sales are read-only; users create separate workspaces for their own uploads. The dark visual system uses restrained brass/sage accents, custom SVG charts, and bundled fonts.

## 9. Verification and delivery evidence

The first table records the original dashboard verification run. The account access upgrade was verified separately, as described below.

| Verification | Recorded result |
| --- | --- |
| Python 3.11 backend/model suite, including optional phishing adapter plumbing | 33 passed. |
| Python 3.12 core suite | 32 passed; optional phishing adapter test skipped because its extra dependencies were absent. |
| Real-browser workflow suite | 9 passed. |
| Browser accessibility audit | No serious or critical axe findings on the six audited desktop pages and mobile Overview. This is not a complete accessibility certification. |
| Frontend production build and source formatting | Passed. |
| Python lint/format and Git whitespace checks | Passed. |
| Reminder behavior without browser requests | Persisted notification verified while the backend was running. |
| Docker | Configuration updated; container build/run was not verified because the local Docker daemon was unavailable. |
| GitHub CI | Workflow added; no remote CI execution is claimed because the work was not pushed. |

Tests cover real finance inference and SHAP, anomaly scoring, explicit unavailable models, input rejection, workspace separation, forged sessions, credential rotation, intake pause, retry deduplication, CSV/XLSX ingestion, date/decimal conventions, export/re-import, reminders, and preserving accepted records when forecasting fails.

The clean source archive excludes virtual environments, installed JavaScript dependencies, bytecode, test output, and runtime databases. Required models, attributed compact data, source code, tests, and launch instructions remain included.

## 10. Remaining work and recommended sequence

**Status updated after the account and trained-model integrations, 27 October 2026.** The original list mixed implementation work, user review, outside artifacts, and privacy decisions. Adding authentication completed part of that list; it did not complete every item.

| Original item | Current status and remaining work |
| --- | --- |
| 1. Review the interface and demonstration story | **Automated engineering checks completed; user review pending.** Browser tests exercise public sample switching and uploading/processing a separate sales history through forecasting. The project team still needs to review the actual presentation and confirm that the interface tells the intended story. |
| 2. Supply and evaluate the phishing model | **Artifact integrated and source-split evaluation completed.** The pinned trained model/tokenizer load locally and are connected to the company UI/API. The reconstructed 2,000-email source test split scored 99.00% accuracy, with 15 misses and 5 false alarms. External/temporal validation, training-lineage confirmation, and false-negative review remain open; this is not a universal accuracy claim. |
| 3. Decide the LLM privacy boundary | **Decision pending; external LLM processing disabled.** The current application sends no uploads to an LLM and does not fine-tune a shared LLM. Agree local versus external inference, allowed fields, consent, retention, and logging before enabling a provider. Public availability alone does not establish that data is anonymous or licensed for every use. |
| 4. Add evaluated GenAI schema assistance | **Manual/rule-based mapping and confirmation implemented; GenAI assistance pending.** Alias suggestions, explicit date/decimal conventions, validation, and user confirmation already work. A future LLM should only propose mappings; ambiguous cases need review before validated transformations affect stored records. |
| 5. Strengthen access and deployment for real organizations | **Account access portion completed; operational work remains.** Registration, login/logout, company memberships, owner/member/admin permissions, and admin restrictions on legacy endpoints are implemented. Email verification, password recovery, optional MFA, retention/deletion controls, secure deployment, backup/restore procedures, and organization identity verification remain incomplete. |
| 6. Make processing durable across restarts | **Pending.** Accepted batches and sales records persist in SQLite, but background jobs run in the web process. Work interrupted by a restart is not automatically recovered. Add persisted job claims/status, retries, stale-job recovery, idempotent execution, and a worker that can resume accepted jobs independently of web requests. |
| 7. Broaden evaluation and control model promotion | **Initial evaluation implemented; broader evaluation and model lifecycle pending.** The sales service compares Prophet with a weekly baseline on one final 28-day holdout. Add evaluation over several time windows and relevant sources, retain evaluation reports and model versions, and support controlled promotion/rollback. Per-company XGBoost/Random Forest classifiers require meaningful labeled outcomes before training or deployment can be justified. |

For the college demonstration, the next implementation priority is **item 6**, followed by the multi-window forecast evaluation part of **item 7**. These can be developed locally without selecting an LLM provider. Continue team review under item 1 and broaden the phishing evaluation under item 2 beyond the reconstructed source split. Keep GenAI disabled until item 3 is settled; item 4 can then build on the working manual pipeline.

Before using real company records, complete the remaining identity, retention, deployment, and backup work under item 5. This is a separate readiness requirement from demonstrating the current public-data application.

## 11. Account access upgrade

The former automatic demo session has been replaced by registration, login, and logout. Registration creates a private company and assigns its creator the owner role. There are no default passwords or public admin signup options. Existing public sample companies and older unowned upload workspaces remain stored and are accessible to locally provisioned administrators, who can explicitly assign company ownership.

Passwords use a random salt and scrypt with N=131072, r=8, p=1. Sessions use random HttpOnly cookies and server-side hashed token records with a 12-hour expiration. Logging out deletes the server session, so copying the old cookie does not restore access. Browser writes require a CSRF token and pass an origin check; login failures and registration are rate-limited. Responses containing company data are marked no-store. No passwords or session cookies are saved in browser local storage.

Owners can manage reporting settings, API credentials, and company membership. Members can view, upload, process, and analyze company data. Owners add teammates by their existing registered email, choosing an owner or member role; no invitation email is sent. The last owner cannot be removed. Authorization is checked on every request, so revoked membership cannot keep reading a company through an existing session. API intake keys remain company-scoped and independent of the browser login.

Administrators are created or promoted using the local `scripts.create_admin` command. They alone can select any company and access legacy experimental finance/security endpoints and Model Lab. The anonymous `/api/demo/session` endpoint is removed, and bootstrap data requires authentication. During upgrade, keys issued through the former open switcher are revoked once; owners/admins issue replacement keys. Stored sales data is preserved.

Upgrade verification passed 40 core backend/model checks on Python 3.11 and 3.12, including a targeted migration check in addition to the full-suite run. One optional phishing-adapter test was skipped on each interpreter because its extra dependencies were absent. All 12 real-browser workflows passed, including registration/login/logout, session loss, role visibility, owner-managed team access, revocation, existing ingestion flows, and desktop/mobile accessibility audits. Local administrator creation and promotion were also checked against a temporary database, preserving existing passwords.

This upgrade does not verify email ownership or legal company identity and does not add password recovery or MFA. Confirm a teammate's identity before granting access. The SQLite database remains unencrypted at the application layer. HTTPS, secure configuration, data retention, backups, and operational review are still needed before deployment with real company records.

Design references: [OWASP Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html) and [OWASP Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html). These references do not constitute a security certification.

## 12. Running and reviewing the delivery

```bash
cd /private/tmp/decisioniq-integration
./scripts/run_local.sh
```

After startup, open `http://127.0.0.1:8082`. The script installs locked dependencies, builds the frontend, verifies/installs the pinned phishing model, and starts the local backend. Set `INSTALL_PHISHING=0` for a core-only installation. The temporary verification servers were stopped after testing, so the launch command is required to reopen the application.

For source-level details, see `README.md`, `docs/PRODUCT_SCOPE.md`, the dashboard modules, and the test suites. The report describes the implementation as reviewed; unresolved features above remain future work.

To review the all-company administration view, register an account and promote it locally, then sign in again or reload:

```bash
uv run python -m scripts.create_admin --email your-account@example.com --promote
```
