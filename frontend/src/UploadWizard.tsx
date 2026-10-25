import { useRef, useState } from 'react';
import { ArrowLeft, ArrowRight, Check, FileSpreadsheet, Upload } from 'lucide-react';
import { api, number, shortDate } from './api';
import { Dialog, ErrorBox, Spinner, Success } from './components';
import type { Batch, Company, Validation } from './types';

const fields = [
  ['date', 'Transaction date', 'Required'],
  ['sales', 'Sales amount', 'Or map units × price'],
  ['record_id', 'Record ID', 'Recommended for deduplication'],
  ['product_id', 'Product code', 'Optional'],
  ['product', 'Product name', 'Optional'],
  ['units', 'Units / quantity', 'Optional'],
  ['unit_price', 'Unit price', 'Used when sales amount is absent'],
  ['currency', 'Currency column', 'Optional'],
];
export default function UploadWizard({
  company,
  existing,
  onClose,
  onProcessed,
  onWorkspace,
}: {
  company: Company;
  existing?: Batch;
  onClose: () => void;
  onProcessed: () => void;
  onWorkspace: (id: string) => Promise<void>;
}) {
  const [step, setStep] = useState(existing ? 1 : 0),
    [batch, setBatch] = useState<Batch | null>(existing || null);
  const [mapping, setMapping] = useState<Record<string, string>>(existing?.options?.mapping || {});
  const [file, setFile] = useState<File | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  const [validation, setValidation] = useState<Validation | null>(null),
    [complete, setComplete] = useState(false),
    [dateFormat, setDateFormat] = useState('iso'),
    [numberFormat, setNumberFormat] = useState('decimal_point');
  const [workspace, setWorkspace] = useState(''),
    [currency, setCurrency] = useState(company.currency);
  const input = useRef<HTMLInputElement>(null);
  const needsWorkspace = company.source_kind === 'public';
  async function submitFile() {
    if (!file) {
      setError('Choose a CSV or Excel file first.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      if (needsWorkspace) {
        if (workspace.trim().length < 2)
          throw new Error('Name the new workspace before uploading.');
        const created = await api<Company>('/companies', {
          method: 'POST',
          body: JSON.stringify({ name: workspace, currency }),
        });
        await onWorkspace(created.id);
      }
      const form = new FormData();
      form.append('file', file);
      const result = await api<Batch>('/uploads', { method: 'POST', body: form });
      setBatch(result);
      setMapping(result.options?.mapping || {});
      setStep(1);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function validate() {
    setBusy(true);
    setError('');
    try {
      const result = await api<Validation>(`/batches/${batch!.id}/validate`, {
        method: 'POST',
        body: JSON.stringify({
          mapping,
          currency,
          calendar_complete: complete,
          date_format: dateFormat,
          number_format: numberFormat,
        }),
      });
      setValidation(result);
      if (!result.error_count) setStep(2);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function process() {
    setBusy(true);
    setError('');
    try {
      await api(`/batches/${batch!.id}/process`, { method: 'POST' });
      onProcessed();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog title="Bring your sales into focus" eyebrow="DATA IMPORT" wide onClose={onClose}>
      <div className="wizard-steps">
        {['Choose a file', 'Review mapping', 'Process data'].map((label, i) => (
          <div className={step === i ? 'current' : step > i ? 'done' : ''} key={label}>
            <span>{step > i ? <Check size={13} /> : `0${i + 1}`}</span>
            {label}
          </div>
        ))}
      </div>
      <div className="dialog-body">
        {error && <ErrorBox>{error}</ErrorBox>}
        {step === 0 && (
          <>
            {needsWorkspace && (
              <div className="import-workspace">
                <p className="body-small">
                  The public sample stays intact. Your file will be analyzed in a separate
                  workspace.
                </p>
                <div className="form-grid">
                  <label>
                    Workspace name
                    <input
                      value={workspace}
                      onChange={(e) => setWorkspace(e.target.value)}
                      placeholder="e.g. Juniper Studio"
                      maxLength={50}
                    />
                  </label>
                  <label>
                    File currency
                    <select value={currency} onChange={(e) => setCurrency(e.target.value)}>
                      {['GBP', 'USD', 'EUR', 'INR', 'AUD', 'CAD', 'JPY'].map((c) => (
                        <option key={c}>{c}</option>
                      ))}
                    </select>
                  </label>
                </div>
              </div>
            )}
            <input
              ref={input}
              type="file"
              accept=".csv,.xlsx"
              className="file-input"
              aria-label="Choose sales file"
              onChange={(e) => {
                setFile(e.target.files?.[0] || null);
                setError('');
              }}
            />
            <button
              className={`dropzone ${file ? 'selected' : ''}`}
              onClick={() => input.current?.click()}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                setFile(e.dataTransfer.files[0] || null);
              }}
            >
              <span className="upload-glyph">
                {file ? (
                  <FileSpreadsheet size={26} strokeWidth={1.25} />
                ) : (
                  <Upload size={26} strokeWidth={1.25} />
                )}
              </span>
              <strong>{file ? file.name : 'Drop your sales file here'}</strong>
              <span>
                {file
                  ? `${number(file.size / 1024)} KB · click to change file`
                  : 'or choose a file from your device'}
              </span>
              <small>CSV or XLSX · up to 5 MB · 25,000 rows</small>
            </button>
            <div className="import-help">
              <FileSpreadsheet size={17} />
              <p>
                Start with dates and sales amounts. Product names, units, and stable transaction IDs
                add more context.
              </p>
              <a href="/api/upload-template.csv" download>
                Get template <ArrowRight size={13} />
              </a>
            </div>
            <p className="privacy-note">
              Files stay in this local application. No external LLM processing is enabled.
            </p>
          </>
        )}
        {step === 1 && batch && (
          <>
            <div className="mapping-intro">
              <div>
                <h3>Match your columns</h3>
                <p>Suggestions use column names. Confirm their meaning before continuing.</p>
              </div>
              <span className="mono muted">{number(batch.row_count)} rows</span>
            </div>
            <div className="mapping-grid">
              {fields.map(([key, label, hint]) => (
                <label key={key}>
                  <span>
                    {label}
                    <small>{hint}</small>
                  </span>
                  <select
                    aria-label={label}
                    value={mapping[key] || ''}
                    onChange={(e) => {
                      setMapping({ ...mapping, [key]: e.target.value });
                      setValidation(null);
                    }}
                  >
                    <option value="">Not mapped</option>
                    {batch.columns?.map((column) => (
                      <option key={column} value={column}>
                        {column}
                      </option>
                    ))}
                  </select>
                </label>
              ))}
            </div>
            <div className="mapping-options">
              <div className="form-grid">
                <label>
                  Date order
                  <select
                    value={dateFormat}
                    onChange={(e) => {
                      setDateFormat(e.target.value);
                      setValidation(null);
                    }}
                  >
                    <option value="iso">ISO · YYYY-MM-DD</option>
                    <option value="day_first">Day first · DD/MM/YYYY</option>
                    <option value="month_first">Month first · MM/DD/YYYY</option>
                  </select>
                </label>
                <label>
                  Number convention
                  <select
                    value={numberFormat}
                    onChange={(e) => {
                      setNumberFormat(e.target.value);
                      setValidation(null);
                    }}
                  >
                    <option value="decimal_point">Decimal point · 1,234.56</option>
                    <option value="decimal_comma">Decimal comma · 1.234,56</option>
                  </select>
                </label>
              </div>
              <label className="check-label">
                <input
                  type="checkbox"
                  checked={complete}
                  onChange={(e) => setComplete(e.target.checked)}
                />
                Days without rows represent zero sales
              </label>
              <p>
                Leave the second option off if missing days could mean missing records. Forecasting
                will explain any coverage gaps.
              </p>
            </div>
            {validation && validation.error_count > 0 && (
              <ErrorBox>
                <strong>{validation.error_count} rows need attention</strong>
                {validation.errors.slice(0, 4).map((item, index) => (
                  <p key={index}>
                    Row {item.row}: {item.message}
                  </p>
                ))}
              </ErrorBox>
            )}
            <h4 className="eyebrow preview-label">FILE PREVIEW</h4>
            <div className="table-scroll raw-preview">
              <table>
                <thead>
                  <tr>
                    {batch.columns?.slice(0, 6).map((column) => (
                      <th key={column}>{column}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {batch.preview?.slice(0, 3).map((row, i) => (
                    <tr key={i}>
                      {batch.columns?.slice(0, 6).map((column) => (
                        <td key={column}>{String(row[column] ?? '—')}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
        {step === 2 && validation && (
          <>
            <Success>Mapping validated. Your data is ready to process.</Success>
            <div className="import-summary">
              <div>
                <span>VALID OBSERVATIONS</span>
                <strong>{number(validation.valid_rows)}</strong>
              </div>
              <div>
                <span>DATA PERIOD</span>
                <strong className="smaller">
                  {shortDate(validation.date_start, true)} — {shortDate(validation.date_end, true)}
                </strong>
              </div>
              <div>
                <span>CURRENCY</span>
                <strong>{currency}</strong>
              </div>
            </div>
            {validation.warnings.map((w) => (
              <div className="notice" key={w}>
                {w}
              </div>
            ))}
            <p className="body-small">
              Processing saves accepted observations, skips exact duplicates, and evaluates sales
              forecasting when the history supports it. Missing financial information is never
              filled with sample-company defaults.
            </p>
          </>
        )}
      </div>
      <div className="dialog-footer">
        <button
          className="button ghost"
          disabled={busy}
          onClick={step > 0 ? () => setStep(step - 1) : onClose}
        >
          {step > 0 && <ArrowLeft size={15} />}
          {step > 0 ? 'Back' : 'Cancel'}
        </button>
        <button
          className="button primary"
          disabled={busy || (step === 0 && !file)}
          onClick={step === 0 ? submitFile : step === 1 ? validate : process}
        >
          {busy ? (
            <Spinner label={step === 2 ? 'Processing' : 'Checking'} />
          ) : (
            <>
              {step === 0 ? 'Review columns' : step === 1 ? 'Validate mapping' : 'Process data'}
              <ArrowRight size={15} />
            </>
          )}
        </button>
      </div>
    </Dialog>
  );
}
