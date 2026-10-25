# ForeSight demonstration scope

This records the agreed requirements and implementation boundaries as of October 25, 2026. The local dashboard implements sales ingestion/analysis, independent security signals, company-scoped demo workspaces, and in-app reporting reminders. Items described as future capabilities remain outside the current demonstration.

## Confirmed requirements

- The first release is a college demonstration using sample companies and public datasets.
- Deliver an actual dashboard, rather than API documentation.
- Support file uploads and company applications pushing data to an authenticated intake API, including login events at login time.
- Financial outputs must have a practical interpretation supported by the available data. The primary feature is a sales outlook: expected higher/lower sales periods, trends, and product demand where sufficient history exists. Cash-flow forecasting is not the primary feature.
- Add recurring company reminders for missing or unprocessed data when API intake is paused, and for overdue upload-only companies. API-active companies receive connection/freshness status rather than the paused-intake upload reminder.
- The primary dashboard serves a company user; a separately identified demo/admin mode can switch among sample companies.
- External LLM processing is undecided. Do not send company uploads to an external LLM while that decision remains open.
- Continue using the separate integration checkout. Publishing has not been authorized; the earlier GitHub push was rejected by automatic approval review.

## Implemented account boundary

Registration creates a private company and owner membership. Owners manage team access and credentials; members can upload and analyze data. Administrators are provisioned by a trusted local CLI and can access public sample companies and Model Lab. Sessions are revocable server-side, cookie writes use CSRF protection, and the anonymous demo-session bypass is removed. Existing uploaded company records are preserved; only an administrator can explicitly assign ownership of an older unowned workspace. Legacy prototype endpoints require an admin session.

## Data intake

Upload and API ingestion must converge on the same company-scoped validation and processing pipeline:

1. Establish company identity through the authenticated account or scoped API credential.
2. Receive files or events and record source, receipt time, reporting period, and schema version.
3. Propose a mapping into a versioned domain schema; require confirmation for ambiguous meanings.
4. Validate types, currency, time zone, missing fields, reporting periods, and business meaning.
5. Save accepted records with provenance and deduplicate retries across both input routes.
6. Mark the batch ready for processing or explain why processing is blocked.

The dashboard supports CSV and XLSX. Other file types can be added explicitly with parsers and preview support. Unsupported inputs must receive a useful message instead of an invented interpretation.

The dashboard implements separate schemas for sales transactions, login events, and email analysis. Monthly financial summaries, receivables, and cash scenarios remain future capabilities. Shared field names do not make their meanings interchangeable. Preserve missing values; never silently substitute the existing demonstration SME defaults for missing uploaded company data.

Treat the reporting period and data coverage separately from the upload timestamp. Re-uploading an old file does not make its financial period current. Late-arriving events must not overwrite newer observations.

Company applications may push a login event when a login happens. Financial updates follow their own agreed daily, weekly, or monthly schedule. Opening the dashboard should display persisted results and freshness; it should not trigger training.

## Financial capability rules

| Available evidence | Supported result | Required limitation |
| --- | --- | --- |
| Dated sales transactions and currency | Historical sales totals, trends, and evaluated sales forecasting | Sales do not establish payment collection or cash availability |
| Matched-period reported revenue and operating expenses | Revenue less reported expenses and expense ratio | Do not label this audited net profit or cash flow |
| Invoice due dates, outstanding amounts, and payment status | Overdue amounts and receivables aging | Do not infer collection timing from an invoice date alone |
| Opening cash and dated expected receipts/payments | Scenario projection of cash balance and possible shortfall dates | Show assumptions, coverage, and forecast period; this is not a calibrated probability |
| Prototype labeled cash-stress data | Experimental XGBoost score and SHAP contributors | Do not present the score as a validated probability for an uploaded company |
| Insufficient or incompatible data | Explain missing fields and available alternatives | Suppress unsupported metrics rather than filling zeros or fabricating values |

The dashboard sample comes from UCI Online Retail, covers 2010–2011, and retains GBP prices and signed quantities, including returns/cancellations. It uses twelve selected merchandise SKUs per customer-country segment and excludes postage/manual adjustment codes. It represents net recorded sales of a selected subset, not complete company revenue or cash inflow. The three fictional workspaces are segments of one public retailer, not three observed independent businesses. The legacy finance endpoint retains its separate original positive-sales aggregate. Company histories remain separate.

Public datasets should retain their provenance, license, native currency, reporting period, and known limitations. Constructed sample-company scenarios must be labeled synthetic. Do not join unrelated public datasets into a supposedly observed company history.

Until target-company outcomes exist, retain the existing classifier as an experimental demonstration. Do not claim per-company training or calibrated company risk based solely on a profile or a short financial series. Forecasts can be fit per eligible series and evaluated against a simple historical baseline before use.

Keep finance and security indicators separately visible. Any combined index must display its calculation policy and input coverage; it must not be presented as a probability of business failure.

## Model and GenAI responsibilities

- Schema assistance proposes mappings from metadata and permitted samples. Approved transformations execute as ordinary validated code.
- Predictive services calculate their own outputs; the LLM does not supply missing financial facts or labels.
- Narrative generation uses the selected company's evidence package, including data gaps, timestamps, and model provenance.
- With no LLM provider selected, manual/rule-based mappings and deterministic evidence summaries remain usable and must be identified accurately.
- Model iterations use reviewed outcomes and held-out evaluation. Register candidates separately and promote only after comparison, retaining the preceding version for rollback.
- Publicly available data is not automatically free of personal information or redistribution constraints. Keep source permissions and data minimization in scope.

## Reminder behavior

Track intake state, next required reporting period, accepted data coverage, processing state, reminder history, and snooze settings separately. API pause alone does not mean data is overdue.

| Condition | Proposed behavior |
| --- | --- |
| API active, current data | No upload reminder |
| API active, data overdue | Show connection/freshness status; do not send the paused-intake upload reminder |
| API paused, data current | Show pause status; wait until the next due date |
| API paused, required data missing and overdue | Remind to upload the missing period or resume intake |
| Upload-only company, required data missing and overdue | Remind to upload the missing reporting period |
| Upload-only company, relevant data received but unprocessed | Remind to resolve validation or process the existing batch |
| API paused, relevant data uploaded but unprocessed | Remind to resolve validation or process the existing batch; do not request a duplicate upload |
| API paused, data processed successfully | Clear that reminder when the required reporting period is covered |

Use in-app notifications first. Cadence defaults to 24 hours and is configurable from 1–168 hours. Due dates and required coverage are editable; the interface supports 24-hour snooze and resume. Reminders persist server-side, with checks every 30 seconds while the backend runs. Quiet hours and delivery escalation are not implemented. No real email/SMS delivery is authorized by this specification. The scheduler must evaluate persisted state while the dashboard is closed; a browser-only timer is insufficient.

## Sales outlook interpretation

- Prioritize recorded sales value and units, seasonality, expected higher/lower sales periods, and category/product analysis where enough observations exist.
- Display native currency, date range, data source, prediction intervals, historical backtest error, and the analysis cutoff. Historical public datasets must forecast from their actual historical cutoff, not from the current calendar date.
- Compare forecasting performance with a simple historical or seasonal baseline. Show insufficient evidence if a more complex model does not earn its place.
- Sales records do not establish customer payment collection, expenses, profit, available cash, or inventory stockouts. Do not calculate those fields without their specific supporting inputs.
- Product units and sales value are separate targets; a high-value product need not have the highest unit demand. Sparse products can be grouped into categories or withheld from detailed forecasts.
- What-if scenarios are conditional arithmetic on explicit assumptions, such as volume changes at unchanged prices. Do not imply that changing prices will have no effect on demand unless the scenario explicitly assumes that.
- The existing XGBoost cash-stress demonstration and SHAP can remain in a clearly labeled demo/model-lab view. They must not supply the primary company-facing health claim without representative validation.

## Implemented dashboard areas

1. Overview: company, data period, freshness, supported finance/security indicators, and source badges.
2. Data hub: uploads, API setup, pause/resume, schema review, validation, and processing history.
3. Sales outlook: supported metrics, dataset-specific sales forecasts, higher/lower sales periods, product analysis, assumptions, and scenarios. Place the experimental cash-stress model in a separate demo/model-lab view.
4. Security: login events, anomaly results, email analysis, and unavailable-model states.
5. Insights: evidence-grounded explanations and actions supported by the supplied records.
6. Activity: processing status, due data periods, reminders, and snooze controls.

## Decisions still needed

- Companies configure their reporting due dates, coverage, and reminder cadence in Activity. There is no inferred reporting schedule from public sales records.
- Select the LLM privacy boundary and provider before enabling external processing. Current schema suggestions use aliases plus manual confirmation; narratives use deterministic templates.
- Obtain the trained phishing artifact to enable email predictions.
- Account authentication and company membership now exist. Email verification, password recovery, MFA, organization verification, and production operations remain future work.

## Sources

- User's original DecisionIQ Risk Review deck, especially architecture slide 6 and prototype screenshot slide 8.
- UCI Online Retail: https://archive.ics.uci.edu/dataset/352/online%2Bretail
- IAS 7 overview, distinguishing cash movements from profit/loss: https://www.ifrs.org/issued-standards/list-of-standards/ias-7-statement-of-cash-flows/
- Prophet historical forecast evaluation: https://facebook.github.io/prophet/docs/diagnostics.html
