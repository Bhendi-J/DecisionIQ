import { useState } from 'react';
import {
  Activity,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  Bell,
  CalendarDays,
  Check,
  Clock3,
  Copy,
  Database,
  Download,
  FileSpreadsheet,
  Fingerprint,
  FlaskConical,
  Info,
  KeyRound,
  Link2,
  Mail,
  Package,
  Pause,
  Play,
  Plus,
  RefreshCw,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  Upload,
} from 'lucide-react';
import { api, csrfHeaders, download, money, number, shortDate, time } from './api';
import Chart from './Chart';
import {
  Badge,
  Dialog,
  Empty,
  ErrorBox,
  Panel,
  ProductTable,
  Spinner,
  TextLink,
} from './components';
import type { Batch, Company, Dashboard, Page } from './types';

type Props = {
  data: Dashboard;
  go: (page: Page) => void;
  upload: (batch?: Batch) => void;
  refresh: () => Promise<void>;
  toast: (value: string) => void;
  horizon: number;
};
export function Metrics({ data, horizon }: Pick<Props, 'data' | 'horizon'>) {
  const { metrics: m, company: c } = data;
  return (
    <div className="metrics-grid">
      <div className="metric">
        <span className="metric-label">
          Recorded sales <span>LAST 30 DAYS</span>
        </span>
        <strong>{money(m.sales_30d, c.currency)}</strong>
        <p>
          <span
            className={
              m.sales_change_pct != null && m.sales_change_pct >= 0 ? 'positive' : 'negative'
            }
          >
            {m.sales_change_pct == null ? (
              '—'
            ) : (
              <>
                {m.sales_change_pct >= 0 ? (
                  <ArrowUpRight size={13} />
                ) : (
                  <ArrowDownRight size={13} />
                )}
                {Math.abs(m.sales_change_pct)}%
              </>
            )}
          </span>{' '}
          vs. previous 30 days
        </p>
      </div>
      <div className="metric">
        <span className="metric-label">
          Expected sales <span>NEXT {horizon} DAYS</span>
        </span>
        <strong>{money(m.expected_sales, c.currency)}</strong>
        <p>
          <span className="tiny-dot brass" />
          {data.forecast.status === 'ready'
            ? data.forecast.model
            : 'Waiting for sufficient history'}
        </p>
      </div>
      <div className="metric">
        <span className="metric-label">
          Units recorded <span>LAST 30 DAYS</span>
        </span>
        <strong>{number(m.units_30d)}</strong>
        <p>
          {m.units_30d == null
            ? 'Quantity data is not available'
            : 'Across the selected sales period'}
        </p>
      </div>
      <div className="metric">
        <span className="metric-label">
          Login signals <span>RECENT EVENTS</span>
        </span>
        <strong>
          {number(m.anomalies)}
          <small> / {number(m.login_events)}</small>
        </strong>
        <p>
          <span className="tiny-dot sage" />
          {m.login_events ? 'Flagged by anomaly detection' : 'No login events received'}
        </p>
      </div>
    </div>
  );
}
export function ForecastPanel({ data, full = false }: { data: Dashboard; full?: boolean }) {
  return (
    <Panel
      title="Sales performance"
      eyebrow={full ? 'HISTORICAL + EXPECTED' : undefined}
      className="forecast-panel"
      action={
        <div className="chart-legend">
          <span>
            <i className="legend-line actual" />
            Recorded
          </span>
          <span>
            <i className="legend-line expected" />
            Expected
          </span>
          <span className="hide-small">
            <i className="legend-band" />
            Indicative range
          </span>
        </div>
      }
    >
      <div className="chart-context">
        <span>
          {data.data_end
            ? `${shortDate(data.data_end, true)} analysis cutoff`
            : 'Your data, once processed'}
        </span>
        <span className="mono">{data.company.currency}</span>
      </div>
      <Chart
        history={data.historical}
        future={data.forecast.future}
        currency={data.company.currency}
      />
      <div className="chart-footer">
        <span>
          <Info size={12} />
          {data.forecast.status === 'ready'
            ? `${data.forecast.model} · held-out MAE ${money(data.forecast.mae, data.company.currency)} per day`
            : data.forecast.message}
        </span>
        {data.forecast.status === 'ready' && <span>28-day evaluation</span>}
      </div>
    </Panel>
  );
}
export function Overview(props: Props) {
  const { data: d, go } = props;
  const ready = d.forecast.status === 'ready';
  const daily = d.forecast.future.map((point) => point.sales);
  return (
    <>
      <Metrics data={d} horizon={props.horizon} />
      <div className="overview-top">
        <ForecastPanel data={d} />
        <Panel
          title="The outlook"
          className="outlook-panel"
          action={
            <span className="outline-icon">
              <ArrowUpRight size={18} />
            </span>
          }
        >
          <p className="outlook-kicker">AHEAD OF THE CURVE</p>
          {d.strongest_week ? (
            <>
              <h3>
                Know when to
                <br />
                lean in.
              </h3>
              <p className="outlook-copy">
                Your strongest expected sales window in this outlook begins{' '}
                <strong>{shortDate(d.strongest_week.start)}</strong>.
              </p>
              <div className="outlook-estimate">
                <span>EXPECTED WEEKLY SALES</span>
                <strong>{money(d.strongest_week.sales, d.company.currency)}</strong>
                <small>
                  {shortDate(d.strongest_week.start)} — {shortDate(d.strongest_week.end, true)}
                </small>
              </div>
            </>
          ) : ready ? (
            <>
              <h3>
                A weekly rhythm.
                <br />A clearer plan.
              </h3>
              <p className="outlook-copy">
                Daily sales vary, while complete weeks have similar expected totals. There is no
                distinct weekly peak in this outlook.
              </p>
              <div className="outlook-estimate">
                <span>EXPECTED DAILY SALES SPAN</span>
                <strong className="daily-span">
                  {money(Math.min(...daily), d.company.currency)} —{' '}
                  {money(Math.max(...daily), d.company.currency)}
                </strong>
                <small>Point estimates · view the indicative range</small>
              </div>
            </>
          ) : (
            <>
              <h3>
                A clearer view
                <br />
                starts with data.
              </h3>
              <p className="outlook-copy">
                Add dated sales records to reveal historical performance and evaluate a sales
                outlook.
              </p>
            </>
          )}
          <button className="outlook-link" onClick={() => go('sales')}>
            Explore sales outlook <ArrowRight size={16} />
          </button>
        </Panel>
      </div>
      <div className="overview-bottom">
        <Panel
          title="Products in focus"
          action={<TextLink onClick={() => go('sales')}>View all products</TextLink>}
        >
          {d.products.length ? (
            <ProductTable products={d.products} currency={d.company.currency} short />
          ) : (
            <Empty
              icon={Package}
              title="No products yet"
              detail="Map product names or codes when importing sales data."
            />
          )}
        </Panel>
        <Panel
          title="Operational signals"
          action={<TextLink onClick={() => go('activity')}>View activity</TextLink>}
        >
          <div className="signal-list">
            <div className="signal-row">
              <span className="signal-icon">
                <Link2 size={17} />
              </span>
              <div>
                <strong>Data intake</strong>
                <p>
                  {d.company.api_state === 'active'
                    ? 'Company API is accepting events'
                    : d.company.api_state === 'paused'
                      ? 'API intake is paused'
                      : 'Manual uploads are your active source'}
                </p>
              </div>
              <Badge tone={d.company.api_state === 'active' ? 'sage' : 'neutral'}>
                {d.company.api_state === 'active'
                  ? 'Active'
                  : d.company.api_state === 'paused'
                    ? 'Paused'
                    : 'Uploads'}
              </Badge>
            </div>
            <div className="signal-row">
              <span className="signal-icon">
                <ShieldCheck size={17} />
              </span>
              <div>
                <strong>Login analysis</strong>
                <p>
                  {d.metrics.login_events
                    ? `${d.metrics.login_events} recent events · provenance attached`
                    : 'No company login events received'}
                </p>
              </div>
              <Badge tone="sage">Available</Badge>
            </div>
            <div className="signal-row">
              <span className="signal-icon">
                <Mail size={17} />
              </span>
              <div>
                <strong>Email analysis</strong>
                <p>
                  {d.phishing_status === 'ready'
                    ? 'Local phishing model is loaded'
                    : 'Trained phishing artifact is not installed'}
                </p>
              </div>
              <Badge tone={d.phishing_status === 'ready' ? 'sage' : 'brass'}>
                {d.phishing_status === 'ready' ? 'Ready' : 'Setup needed'}
              </Badge>
            </div>
          </div>
          <div className="signal-note">
            <span className="tiny-dot brass" />
            <span>Sales and security remain separate, evidence-led signals.</span>
          </div>
        </Panel>
      </div>
      {d.reminders.length > 0 &&
        !(d.company.snoozed_until && new Date(d.company.snoozed_until).getTime() > Date.now()) && (
          <div className="reminder-strip">
            <Bell size={17} />
            <div>
              <strong>{d.reminders[0].title}</strong>
              <span>{d.reminders[0].detail}</span>
            </div>
            <button className="text-link" onClick={() => go('activity')}>
              Review <ArrowRight size={14} />
            </button>
          </div>
        )}
    </>
  );
}
export function Sales(props: Props) {
  const { data: d } = props;
  const [volume, setVolume] = useState(0),
    [price, setPrice] = useState(0),
    [tab, setTab] = useState<'outlook' | 'evaluation'>('outlook');
  const expected = d.metrics.expected_sales;
  const scenario = expected == null ? null : expected * (1 + volume / 100) * (1 + price / 100);
  return (
    <>
      <Metrics data={d} horizon={props.horizon} />
      <div className="subtabs">
        <button className={tab === 'outlook' ? 'selected' : ''} onClick={() => setTab('outlook')}>
          Sales outlook
        </button>
        <button
          className={tab === 'evaluation' ? 'selected' : ''}
          onClick={() => setTab('evaluation')}
        >
          Model evaluation
        </button>
      </div>
      {tab === 'outlook' ? (
        <>
          <ForecastPanel data={d} full />
          <div className="two-columns">
            <Panel title="Plan around the quieter week" eyebrow="EXPECTED SALES WINDOW">
              <div className="window-data">
                <span className="window-icon">
                  <CalendarDays size={25} strokeWidth={1.2} />
                </span>
                <div>
                  <strong>
                    {d.quietest_week
                      ? `${shortDate(d.quietest_week.start)} — ${shortDate(d.quietest_week.end)}`
                      : d.forecast.status === 'ready'
                        ? 'No distinct weekly low'
                        : 'Not enough history'}
                  </strong>
                  <p>
                    {d.quietest_week
                      ? money(d.quietest_week.sales, d.company.currency) +
                        ' expected sales across seven days'
                      : d.forecast.status === 'ready'
                        ? 'Complete forecast weeks have similar expected totals.'
                        : 'A forecast needs reliable, sufficiently long sales history.'}
                  </p>
                </div>
              </div>
              <p className="body-small">
                The lowest-sales complete week within this outlook. This estimate describes sales
                value, not cash availability, profit, or inventory requirements.
              </p>
            </Panel>
            <Panel title="What if things change?" eyebrow="EXPLICIT SCENARIO">
              <div className="scenario-controls">
                <label>
                  <span>
                    Sales volume{' '}
                    <b>
                      {volume > 0 ? '+' : ''}
                      {volume}%
                    </b>
                  </span>
                  <input
                    aria-label="Volume assumption"
                    type="range"
                    min="-50"
                    max="50"
                    value={volume}
                    onChange={(e) => setVolume(Number(e.target.value))}
                  />
                </label>
                <label>
                  <span>
                    Unit price{' '}
                    <b>
                      {price > 0 ? '+' : ''}
                      {price}%
                    </b>
                  </span>
                  <input
                    aria-label="Price assumption"
                    type="range"
                    min="-30"
                    max="30"
                    value={price}
                    onChange={(e) => setPrice(Number(e.target.value))}
                  />
                </label>
              </div>
              <div className="scenario-result">
                <span>Conditional sales estimate</span>
                <strong>{money(scenario, d.company.currency)}</strong>
                <button
                  className="text-link"
                  onClick={() => {
                    setVolume(0);
                    setPrice(0);
                  }}
                >
                  Reset
                </button>
              </div>
              <p className="micro-copy">
                Arithmetic scenario. Assumes unchanged product mix and no demand response to price
                changes.
              </p>
            </Panel>
          </div>
        </>
      ) : (
        <Panel title="Make the model earn its place" eyebrow="HELD-OUT EVALUATION">
          {d.forecast.status === 'ready' ? (
            <>
              <p className="body-small">
                The last 28 days are withheld from training. Prophet competes with a weekly seasonal
                baseline; the lower-error method provides the outlook.
              </p>
              <div className="evaluation-grid">
                <div>
                  <span>SELECTED METHOD</span>
                  <strong className="smaller">{d.forecast.model}</strong>
                </div>
                <div>
                  <span>SEASONAL BASELINE MAE</span>
                  <strong>{money(d.forecast.baseline_mae, d.company.currency)}</strong>
                </div>
                <div>
                  <span>PROPHET MAE</span>
                  <strong>{money(d.forecast.prophet_mae, d.company.currency)}</strong>
                </div>
              </div>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Held-out day</th>
                      <th className="numeric">Actual sales</th>
                      <th className="numeric">Predicted sales</th>
                      <th className="numeric">Absolute error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.forecast.backtest?.map((row) => (
                      <tr key={row.date}>
                        <td>{shortDate(row.date, true)}</td>
                        <td className="numeric">{money(row.actual, d.company.currency)}</td>
                        <td className="numeric">{money(row.predicted, d.company.currency)}</td>
                        <td className="numeric muted">
                          {money(Math.abs(row.actual - row.predicted), d.company.currency)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="panel-footnote">
                Error is measured in {d.company.currency} per day. A single historical evaluation
                does not establish performance for other businesses.
              </div>
            </>
          ) : (
            <Empty
              icon={Activity}
              title="Evaluation is not available yet"
              detail={
                d.forecast.message || 'Process a sufficiently long daily sales history first.'
              }
            />
          )}
        </Panel>
      )}
      <Panel
        title="Product performance"
        eyebrow="RECORDED HISTORY · UP TO 12 PRODUCTS"
        action={
          <a className="button compact ghost" href="/api/export/sales.csv">
            <Download size={14} />
            Export observations
          </a>
        }
      >
        {d.products.length ? (
          <ProductTable products={d.products} currency={d.company.currency} />
        ) : (
          <Empty
            icon={Package}
            title="Your products will appear here"
            detail="Include product names or codes in your next import."
          />
        )}
      </Panel>
      <div className="provenance-line">
        <Database size={14} />
        <span>
          {d.company.source} {d.company.segment && `· ${d.company.segment} segment`} ·{' '}
          {d.company.sales_basis === 'positive_sales_proxy'
            ? 'Positive-sales proxy; canceled invoices and nonpositive quantities excluded.'
            : 'Recorded sales; interpret according to your source accounting basis.'}
        </span>
      </div>
    </>
  );
}
export function DataHub(props: Props) {
  const { data: d, upload, refresh, toast } = props;
  const [key, setKey] = useState(''),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    [showAPI, setShowAPI] = useState(false);
  async function changeState(state: Company['api_state']) {
    setBusy(true);
    setError('');
    try {
      await api('/settings', { method: 'PATCH', body: JSON.stringify({ api_state: state }) });
      await refresh();
      toast(state === 'active' ? 'API intake resumed' : 'API intake paused');
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function rotate() {
    setBusy(true);
    setError('');
    try {
      const result = await api<{ key: string }>('/settings/api-key', { method: 'POST' });
      setKey(result.key);
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      toast('Copied to clipboard');
    } catch {
      setError('Clipboard access is unavailable. Select and copy the text manually.');
    }
  }
  const example = `curl ${window.location.origin}/api/intake/sales \\\n  -H "X-API-Key: $FORESIGHT_API_KEY" \\\n  -H "Content-Type: application/json" \\\n  -d '{"currency":"${d.company.currency}","records":[{"record_id":"order-001","date":"2026-10-01","product":"Example","units":3,"sales":150}]}'`;
  return (
    <>
      {error && <ErrorBox>{error}</ErrorBox>}
      <div className="source-grid">
        <Panel
          title="File uploads"
          eyebrow="YOUR EXPORTS, ONE CLEAR VIEW"
          action={
            <span className="source-icon">
              <FileSpreadsheet size={22} strokeWidth={1.3} />
            </span>
          }
        >
          <p className="body-small">
            Bring sales records from spreadsheets and existing systems. Review every field mapping
            before processing.
          </p>
          <div className="source-tags">
            <span>CSV</span>
            <span>XLSX</span>
            <span>5 MB per file</span>
          </div>
          <button className="button primary" onClick={() => upload()}>
            <Upload size={15} />
            Upload sales data
          </button>
        </Panel>
        <Panel
          title="Company API"
          eyebrow="DATA AT THE SOURCE"
          action={
            <span className="source-icon">
              <Link2 size={22} strokeWidth={1.3} />
            </span>
          }
        >
          <p className="body-small">
            Push sales records and login events directly from your application. Each credential
            belongs to one workspace.
          </p>
          <div className="api-status-row">
            <Badge tone={d.company.api_state === 'active' ? 'sage' : 'neutral'}>
              {d.company.api_state === 'active'
                ? 'Intake active'
                : d.company.api_state === 'paused'
                  ? 'Intake paused'
                  : 'Upload-only mode'}
            </Badge>
            <span>JSON / HTTPS-ready</span>
          </div>
          <div className="button-row">
            <button className="button secondary" onClick={() => setShowAPI(!showAPI)}>
              <KeyRound size={14} />
              {showAPI ? 'Hide integration' : 'Configure integration'}
            </button>
            <button
              className="button ghost"
              disabled={busy || d.company.role === 'member'}
              title={d.company.role === 'member' ? 'Company owners manage API intake' : undefined}
              onClick={() => changeState(d.company.api_state === 'active' ? 'paused' : 'active')}
            >
              {d.company.api_state === 'active' ? <Pause size={14} /> : <Play size={14} />}
              {d.company.api_state === 'active' ? 'Pause' : 'Activate'}
            </button>
          </div>
        </Panel>
      </div>
      {showAPI && (
        <Panel title="Connect your application" eyebrow="WORKSPACE-SCOPED INTAKE">
          <div className="integration-settings">
            <div>
              <h3>API credential</h3>
              <p className="body-small">
                {d.api_key
                  ? `An existing credential begins ${d.api_key.prefix}…`
                  : 'Create a credential to send events into this workspace.'}{' '}
                Rotating revokes the previous key.
              </p>
              <button
                className="button secondary"
                disabled={busy || d.company.role === 'member'}
                onClick={rotate}
              >
                {busy ? (
                  <Spinner />
                ) : (
                  <>
                    <KeyRound size={14} />
                    {d.api_key ? 'Rotate credential' : 'Generate credential'}
                  </>
                )}
              </button>
            </div>
            <div className="integration-endpoints">
              <span>SALES BATCHES</span>
              <code>POST /api/intake/sales</code>
              <span>LOGIN-TIME EVENTS</span>
              <code>POST /api/intake/logins</code>
            </div>
          </div>
          {key && (
            <div className="key-reveal">
              <span>Shown once. Keep it private.</span>
              <div>
                <code>{key}</code>
                <button
                  className="icon-button"
                  aria-label="Copy new API credential"
                  onClick={() => copy(key)}
                >
                  <Copy size={16} />
                </button>
              </div>
            </div>
          )}
          {d.company.source_kind === 'public' && (
            <div className="notice">
              This public sample is read-only. Create an upload workspace before sending sales
              batches; login examples can still be analyzed here.
            </div>
          )}
          <div className="code-heading">
            <span className="eyebrow">EXAMPLE SALES REQUEST</span>
            <button className="text-link" onClick={() => copy(example)}>
              <Copy size={13} />
              Copy request
            </button>
          </div>
          <pre className="code-block">{example}</pre>
          <p className="micro-copy">
            Use stable record IDs for retries. Paused intake returns a clear 409 response; accepted
            batches can be followed in processing history.
          </p>
        </Panel>
      )}
      <Panel
        title="Processing history"
        action={
          <button className="button compact ghost" onClick={refresh}>
            <RefreshCw size={14} />
            Refresh
          </button>
        }
      >
        {d.batches.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Source / file</th>
                  <th>Received</th>
                  <th>Status</th>
                  <th>Result</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {d.batches.map((batch) => (
                  <tr key={batch.id}>
                    <td>
                      <div className="file-cell">
                        <FileSpreadsheet size={16} />
                        <div>
                          <strong>{batch.name}</strong>
                          <small>{batch.source === 'api' ? 'Company API' : 'File upload'}</small>
                        </div>
                      </div>
                    </td>
                    <td className="muted nowrap">{time(batch.received_at)}</td>
                    <td>
                      <Badge
                        tone={
                          batch.status === 'processed'
                            ? 'sage'
                            : batch.status === 'failed'
                              ? 'rose'
                              : 'brass'
                        }
                      >
                        {batch.status.replace('_', ' ')}
                      </Badge>
                    </td>
                    <td className="muted">
                      {batch.status === 'processed' ? (
                        `${batch.result.inserted} new · ${batch.result.duplicates} duplicates`
                      ) : batch.status === 'failed' ? (
                        String(batch.result.error || 'Review validation')
                      ) : batch.status === 'processing' ? (
                        <Spinner label="Preparing analysis" />
                      ) : (
                        'Mapping review required'
                      )}
                    </td>
                    <td>
                      {['needs_mapping', 'ready', 'failed'].includes(batch.status) && (
                        <button
                          className="text-link"
                          onClick={async () => {
                            try {
                              const detail = await api<Batch>(`/batches/${batch.id}`);
                              upload(detail);
                            } catch (err) {
                              toast((err as Error).message);
                            }
                          }}
                        >
                          Review
                          <ArrowRight size={13} />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty
            icon={Database}
            title="A clean slate for your next import"
            detail={
              d.company.source_kind === 'public'
                ? 'The public sample is preloaded. Your own files will live in a separate workspace.'
                : 'Upload a CSV or Excel file, or connect your application to start a processing history.'
            }
            action={
              <button className="button secondary" onClick={() => upload()}>
                <Plus size={14} />
                Import your first file
              </button>
            }
          />
        )}
      </Panel>
      <div className="two-columns">
        <Panel title="What your data can tell you">
          <ul className="capability-list">
            <li>
              <Check size={15} />
              Sales value and unit trends
            </li>
            <li>
              <Check size={15} />
              Product contribution and seasonality
            </li>
            <li>
              <Check size={15} />
              Evaluated forecasts, when history supports them
            </li>
            <li>
              <Info size={15} />
              Cash flow and profit need additional source records
            </li>
          </ul>
        </Panel>
        <Panel title="Source & processing boundary">
          <div className="detail-list">
            <div>
              <span>Current source</span>
              <strong>{d.company.source}</strong>
            </div>
            <div>
              <span>Data period</span>
              <strong>
                {shortDate(d.data_start, true)} — {shortDate(d.data_end, true)}
              </strong>
            </div>
            <div>
              <span>Currency / timezone</span>
              <strong>
                {d.company.currency} / {d.company.timezone}
              </strong>
            </div>
            <div>
              <span>External LLM processing</span>
              <Badge>Disabled</Badge>
            </div>
          </div>
        </Panel>
      </div>
    </>
  );
}

export function Security(props: Props) {
  const { data: d, refresh, toast } = props;
  const [tab, setTab] = useState('logins'),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [login, setLogin] = useState({
    login_hour: 10,
    failed_attempts: 0,
    new_device: 0,
    login_frequency: 5,
    location_difference: 0,
  });
  const [email, setEmail] = useState('');
  async function analyze() {
    setBusy(true);
    setError('');
    setResult(null);
    try {
      const value = await api<Record<string, unknown>>(
        '/security/' + (tab === 'logins' ? 'login' : 'email'),
        { method: 'POST', body: JSON.stringify(tab === 'logins' ? login : { text: email }) },
      );
      setResult(value);
      await refresh();
      toast('Analysis completed');
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="security-summary">
        <div>
          <span className="security-emblem">
            <ShieldCheck size={30} strokeWidth={1.1} />
          </span>
          <div>
            <p className="eyebrow">INDEPENDENT SECURITY SIGNALS</p>
            <h2>Context before conclusions.</h2>
            <p>
              Inspect login behavior and email content without turning separate events into a
              company-wide probability.
            </p>
          </div>
        </div>
        <Badge tone={tab === 'email' && d.phishing_status !== 'ready' ? 'brass' : 'sage'}>
          {tab === 'logins'
            ? 'Login model available'
            : d.phishing_status === 'ready'
              ? 'Email model available'
              : 'Email model setup required'}
        </Badge>
      </div>
      <div className="subtabs">
        <button
          className={tab === 'logins' ? 'selected' : ''}
          onClick={() => {
            setTab('logins');
            setResult(null);
            setError('');
          }}
        >
          <Fingerprint size={15} />
          Login analysis
        </button>
        <button
          className={tab === 'email' ? 'selected' : ''}
          onClick={() => {
            setTab('email');
            setResult(null);
            setError('');
          }}
        >
          <Mail size={15} />
          Email analysis
        </button>
      </div>
      <div className="security-grid">
        <Panel
          title={tab === 'logins' ? 'Examine a login' : 'Examine an email'}
          eyebrow="MANUAL ANALYSIS"
        >
          {tab === 'logins' ? (
            <div className="form-grid login-form">
              {[
                ['login_hour', 'Login hour (0–23)', 0, 23],
                ['failed_attempts', 'Failed attempts', 0, 100],
                ['login_frequency', 'Logins per day', 0, 1000],
              ].map(([key, label, min, max]) => (
                <label key={key}>
                  {' '}
                  {label}
                  <input
                    type="number"
                    min={min}
                    max={max}
                    value={login[key as keyof typeof login]}
                    onChange={(e) => setLogin({ ...login, [key]: Number(e.target.value) })}
                  />
                </label>
              ))}
              {[
                ['new_device', 'New device'],
                ['location_difference', 'Unusual location'],
              ].map(([key, label]) => (
                <label key={key}>
                  {label}
                  <select
                    value={login[key as keyof typeof login]}
                    onChange={(e) => setLogin({ ...login, [key]: Number(e.target.value) })}
                  >
                    <option value="0">No</option>
                    <option value="1">Yes</option>
                  </select>
                </label>
              ))}
            </div>
          ) : (
            <>
              <label className="email-label">
                Email content
                <textarea
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="Paste an email or message to analyze…"
                  maxLength={100000}
                  rows={8}
                />
              </label>
              {d.phishing_status !== 'ready' && (
                <div className="notice">
                  <strong>Trained model required</strong>
                  <p>
                    The trained email classifier is not installed on this server. Run the model
                    installer or configure a local model directory to enable analysis.
                  </p>
                </div>
              )}
            </>
          )}
          {error && <ErrorBox>{error}</ErrorBox>}
          <button
            className="button primary"
            disabled={busy || (tab === 'email' && (!email.trim() || d.phishing_status !== 'ready'))}
            onClick={analyze}
          >
            {busy ? (
              <Spinner label="Analyzing" />
            ) : (
              <>
                <ArrowUpRight size={15} />
                Analyze {tab === 'logins' ? 'login' : 'email'}
              </>
            )}
          </button>
          {result?.truncated === true && (
            <div className="notice">
              Only the first 256 tokens were analyzed. The rest of this message was excluded.
            </div>
          )}
          {result && (
            <div className="analysis-result">
              <Badge tone={result.is_anomaly || result.is_phishing ? 'rose' : 'sage'}>
                {result.is_anomaly || result.is_phishing
                  ? 'Flagged for review'
                  : tab === 'email'
                    ? 'No phishing flag'
                    : 'No anomaly detected'}
              </Badge>
              <strong>
                {String(result.risk_score)}
                <small>/100</small>
              </strong>
              <p>
                {tab === 'logins'
                  ? 'Transformed Isolation Forest score. This is not a calibrated probability of account compromise.'
                  : 'Model score for this message only. An unflagged message can still be malicious.'}
              </p>
            </div>
          )}
        </Panel>
        <Panel title="Reading the signal" eyebrow="MODEL CONTEXT">
          <div className="context-item">
            <span>01</span>
            <div>
              <h3>{tab === 'email' ? 'Message-level evidence' : 'Behavior, not identity'}</h3>
              <p>
                {tab === 'email'
                  ? 'DistilBERT evaluates the wording of the first 256 tokens. Longer messages are truncated, and the result applies to this input only.'
                  : 'Isolation Forest looks for unusual combinations of login hour, failed attempts, device, frequency, and location.'}
              </p>
            </div>
          </div>
          <div className="context-item">
            <span>02</span>
            <div>
              <h3>Review before acting</h3>
              <p>
                {tab === 'email'
                  ? 'An unflagged message can still be malicious. Review the sender and link destinations before trusting a request.'
                  : 'A flag is an investigation signal. Travel, a new device, or unusual working hours can have legitimate explanations.'}
              </p>
            </div>
          </div>
          <div className="context-item">
            <span>03</span>
            <div>
              <h3>Keep provenance attached</h3>
              <p>
                {tab === 'email'
                  ? 'The contributor’s trained export was evaluated on a reconstructed historical CEAS08 test split. Performance can differ on new sources and current company emails.'
                  : 'Preloaded login events are synthetic examples, separate from the UCI sales history. Manually analyzed events are labeled separately.'}
              </p>
            </div>
          </div>
          <div className="context-foot">
            <Info size={14} />
            Email text is not retained after successful analysis; only the result and text length
            are stored.
          </div>
        </Panel>
      </div>
      <Panel
        title="Recent security events"
        action={<span className="mono muted">{number(d.events.length)} EVENTS</span>}
      >
        {d.events.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Event</th>
                  <th>Observed</th>
                  <th>Provenance</th>
                  <th>Signal</th>
                  <th className="numeric">Score</th>
                </tr>
              </thead>
              <tbody>
                {d.events.map((event) => (
                  <tr key={event.id}>
                    <td>
                      <div className="file-cell">
                        {event.kind === 'login' ? <Fingerprint size={16} /> : <Mail size={16} />}
                        <strong>{event.payload.actor || 'Email analysis'}</strong>
                      </div>
                    </td>
                    <td className="muted nowrap">{time(event.occurred_at)}</td>
                    <td className="muted">{event.payload.source}</td>
                    <td>
                      <Badge
                        tone={
                          event.result.is_anomaly || event.result.is_phishing
                            ? 'rose'
                            : event.result.status === 'available'
                              ? 'sage'
                              : 'neutral'
                        }
                      >
                        {event.result.status !== 'available'
                          ? 'Unavailable'
                          : event.result.is_anomaly || event.result.is_phishing
                            ? 'Review'
                            : event.kind === 'email'
                              ? 'Not flagged'
                              : 'Normal'}
                      </Badge>
                    </td>
                    <td className="numeric">
                      {event.result.risk_score ?? '—'}
                      <span className="muted"> / 100</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty
            icon={ShieldCheck}
            title="No security events yet"
            detail="Analyze an example above or connect your application's login events in the Data Hub."
          />
        )}
      </Panel>
    </>
  );
}
export function Insights({ data: d, toast }: Props) {
  function exportReport() {
    const text =
      `${d.company.name} — ForeSight evidence summary\nSource: ${d.company.source}\nAnalysis cutoff: ${d.data_end || 'No sales history'}\nCurrency: ${d.company.currency}\nNarration: deterministic evidence template; no external LLM\n\n` +
      d.insights
        .map((item) => `${item.title}\n${item.body}\nEvidence: ${item.source}\n`)
        .join('\n');
    download(`${d.company.id}-evidence-summary.txt`, text);
    toast('Evidence summary downloaded');
  }
  return (
    <>
      <div className="insight-intro">
        <span className="insight-mark">
          <Info size={28} strokeWidth={1.1} />
        </span>
        <div>
          <p className="eyebrow">GROUNDED IN THE RECORD</p>
          <h2>Understand the story behind the numbers.</h2>
          <p>Every observation below is tied to a calculation, model output, or data limitation.</p>
        </div>
        <button className="button secondary" onClick={exportReport}>
          <Download size={14} />
          Download summary
        </button>
      </div>
      <div className="insights-grid">
        {d.insights.map((item, index) => (
          <article className="insight-card" key={item.title}>
            <div className="insight-top">
              <span className="mono">0{index + 1}</span>
              <Badge tone={item.kind === 'quality' ? 'neutral' : 'brass'}>{item.source}</Badge>
            </div>
            <h3>{item.title}</h3>
            <p>{item.body}</p>
            <div className="insight-evidence">
              <span className="tiny-dot brass" />
              {item.kind === 'quality' ? 'Coverage check' : 'Evidence-backed observation'}
            </div>
          </article>
        ))}
      </div>
      <div className="narration-note">
        <Info size={17} />
        <div>
          <strong>Transparent reporting, by design.</strong>
          <p>
            These are deterministic evidence summaries. External GenAI processing and customer-data
            training are disabled until the privacy boundary and provider are selected.
          </p>
        </div>
      </div>
    </>
  );
}
export function ActivityPage({ data: d, refresh, toast }: Props) {
  const [settings, setSettings] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  const [due, setDue] = useState(d.company.next_due.slice(0, 16)),
    [period, setPeriod] = useState(d.company.expected_period_end),
    [cadence, setCadence] = useState(d.company.reminder_hours);
  async function save() {
    setBusy(true);
    setError('');
    try {
      await api('/settings', {
        method: 'PATCH',
        body: JSON.stringify({
          next_due: new Date(due + 'Z').toISOString(),
          expected_period_end: period,
          reminder_hours: cadence,
        }),
      });
      await refresh();
      setSettings(false);
      toast('Reporting schedule saved');
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function snooze() {
    try {
      await api('/reminders/snooze', {
        method: snoozed ? 'DELETE' : 'POST',
        ...(snoozed ? {} : { body: JSON.stringify({ hours: 24 }) }),
      });
      await refresh();
      toast(snoozed ? 'Reminders resumed' : 'Reminders snoozed for 24 hours');
    } catch (err) {
      toast((err as Error).message);
    }
  }
  const snoozed =
    d.company.snoozed_until && new Date(d.company.snoozed_until).getTime() > Date.now();
  return (
    <>
      <div className="two-columns">
        <Panel
          title="Reporting rhythm"
          eyebrow="DATA FRESHNESS"
          action={
            <button
              className="icon-button"
              aria-label="Edit reporting schedule"
              disabled={d.company.role === 'member'}
              onClick={() => setSettings(true)}
            >
              <Settings2 size={17} />
            </button>
          }
        >
          <div className="detail-list">
            <div>
              <span>Next update due</span>
              <strong>{time(d.company.next_due)} IST</strong>
            </div>
            <div>
              <span>Required coverage through</span>
              <strong>{shortDate(d.company.expected_period_end, true)}</strong>
            </div>
            <div>
              <span>Repeat reminder</span>
              <strong>Every {d.company.reminder_hours} hours while overdue</strong>
            </div>
            <div>
              <span>Intake mode</span>
              <Badge tone={d.company.api_state === 'active' ? 'sage' : 'neutral'}>
                {d.company.api_state.replace('_', ' ')}
              </Badge>
            </div>
          </div>
          <p className="micro-copy">
            The server evaluates reporting schedules even when this dashboard is closed.
            Notifications remain inside this application.
          </p>
        </Panel>
        <Panel
          title="Reminders"
          eyebrow={snoozed ? 'SNOOZED' : 'ACTION WHEN IT MATTERS'}
          action={
            <button className="text-link" onClick={snooze}>
              <Clock3 size={14} />
              {snoozed ? 'Resume reminders' : 'Snooze 24h'}
            </button>
          }
        >
          {snoozed ? (
            <div className="calm-state">
              <Clock3 size={24} />
              <h3>A little breathing room.</h3>
              <p>Reminders resume after {time(d.company.snoozed_until!)} IST.</p>
            </div>
          ) : d.reminders.length ? (
            <div className="reminder-list">
              {d.reminders.slice(0, 3).map((item) => (
                <div key={item.id}>
                  <span className="reminder-icon">
                    <Bell size={15} />
                  </span>
                  <div>
                    <strong>{item.title}</strong>
                    <p>{item.detail}</p>
                    <small>{time(item.created_at)} IST</small>
                  </div>
                  {!item.read_at && (
                    <button
                      className="icon-button"
                      aria-label="Mark reminder read"
                      onClick={async () => {
                        await api(`/reminders/${item.id}/read`, { method: 'POST' });
                        await refresh();
                      }}
                    >
                      <Check size={15} />
                    </button>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="calm-state">
              <Check size={24} />
              <h3>Nothing needs your attention.</h3>
              <p>
                {d.company.api_state === 'active'
                  ? 'API intake is active. Any missing coverage appears as connection status, rather than an upload reminder.'
                  : 'Your next reminder appears only when data or processing is overdue.'}
              </p>
            </div>
          )}
        </Panel>
      </div>
      <Panel
        title="Workspace activity"
        action={
          <button className="button ghost compact" onClick={refresh}>
            <RefreshCw size={14} />
            Refresh
          </button>
        }
      >
        {d.activity.length ? (
          <div className="timeline">
            {d.activity.map((item) => (
              <div className="timeline-item" key={item.id}>
                <span className={`timeline-icon ${item.kind}`}>
                  <Activity size={15} />
                </span>
                <div>
                  <h3>{item.title}</h3>
                  <p>{item.detail || 'Workspace settings were updated.'}</p>
                </div>
                <time>{time(item.created_at)} IST</time>
              </div>
            ))}
          </div>
        ) : (
          <Empty
            icon={Activity}
            title="Your activity starts here"
            detail="Imports, analysis, and configuration changes appear in this timeline."
          />
        )}
      </Panel>
      {settings && (
        <Dialog
          title="Set your reporting rhythm"
          eyebrow="WORKSPACE SCHEDULE"
          onClose={() => setSettings(false)}
        >
          <div className="dialog-body">
            {error && <ErrorBox>{error}</ErrorBox>}
            <div className="form-stack">
              <label>
                Next update due (UTC)
                <input type="datetime-local" value={due} onChange={(e) => setDue(e.target.value)} />
              </label>
              <label>
                Required data coverage through
                <input type="date" value={period} onChange={(e) => setPeriod(e.target.value)} />
              </label>
              <label>
                Repeat overdue reminders
                <select value={cadence} onChange={(e) => setCadence(Number(e.target.value))}>
                  {[1, 6, 12, 24, 48, 72, 168].map((n) => (
                    <option key={n} value={n}>
                      Every {n} hours
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <p className="body-small">
              Upload reminders apply to paused API intake and upload-only workspaces. Upload time
              and reporting-period coverage are tracked separately.
            </p>
          </div>
          <div className="dialog-footer">
            <button className="button ghost" onClick={() => setSettings(false)}>
              Cancel
            </button>
            <button className="button primary" disabled={busy} onClick={save}>
              {busy ? <Spinner /> : 'Save schedule'}
            </button>
          </div>
        </Dialog>
      )}
    </>
  );
}
export function ModelLab({ data: d }: Props) {
  const [revenue, setRevenue] = useState(50000),
    [opex, setOpex] = useState(35000),
    [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  const [result, setResult] = useState<{
    risk_probability: number;
    shap_features: { feature: string; direction: string; magnitude: number }[];
  } | null>(null);
  async function run() {
    setBusy(true);
    setError('');
    try {
      const response = await fetch('/finance/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...csrfHeaders() },
        body: JSON.stringify({ revenue_usd: revenue, opex_usd: opex }),
      });
      const value = await response.json();
      if (!response.ok) throw new Error(value.detail);
      setResult(value);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="notice lab-notice">
        <FlaskConical size={21} />
        <div>
          <strong>A model demonstration, separate from {d.company.name}.</strong>
          <p>
            This XGBoost classifier was trained on prototype/synthetic cash-stress data. Its score
            is not a validated probability for this workspace. Inputs are a separate USD sample
            profile, independent of the sales dashboard.
          </p>
        </div>
      </div>
      <div className="two-columns">
        <Panel title="Explore the original finance model" eyebrow="EXPERIMENTAL">
          <div className="form-stack">
            <label>
              Sample monthly revenue (USD)
              <input
                type="number"
                min="0"
                value={revenue}
                onChange={(e) => setRevenue(Number(e.target.value))}
              />
            </label>
            <label>
              Sample operating expenditure (USD)
              <input
                type="number"
                min="0"
                value={opex}
                onChange={(e) => setOpex(Number(e.target.value))}
              />
            </label>
          </div>
          <p className="micro-copy">
            Other inputs use the model's documented default sample profile. This does not fill
            missing data in your workspace.
          </p>
          {error && <ErrorBox>{error}</ErrorBox>}
          <button className="button secondary" disabled={busy} onClick={run}>
            {busy ? (
              <Spinner />
            ) : (
              <>
                <Play size={14} />
                Run sample profile
              </>
            )}
          </button>
        </Panel>
        <Panel title="Model output & contributors" eyebrow="NATIVE TREESHAP">
          {result ? (
            <>
              <div className="lab-score">
                <strong>
                  {(result.risk_probability * 100).toFixed(1)}
                  <small>/100</small>
                </strong>
                <Badge tone="brass">Experimental score</Badge>
              </div>
              <div className="shap-list">
                {result.shap_features.map((item) => (
                  <div key={item.feature}>
                    <span>{item.feature.replaceAll('_', ' ')}</span>
                    <span className={item.direction === 'increases_risk' ? 'negative' : 'positive'}>
                      {item.direction === 'increases_risk' ? '+' : '−'}
                      {item.magnitude.toFixed(3)}
                    </span>
                  </div>
                ))}
              </div>
              <p className="micro-copy">
                Contributions are in log-odds. They explain the model, and do not establish causal
                effects.
              </p>
            </>
          ) : (
            <Empty
              icon={SlidersHorizontal}
              title="Inspect a sample prediction"
              detail="Run the sample profile to examine the score and the features behind it."
            />
          )}
        </Panel>
      </div>
    </>
  );
}
