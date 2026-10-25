export type Page = 'overview' | 'data' | 'sales' | 'security' | 'insights' | 'activity' | 'lab';
export interface Company {
  role: 'owner' | 'member' | 'admin';
  id: string;
  name: string;
  initials: string;
  segment: string | null;
  currency: string;
  source: string;
  source_kind: string;
  sales_basis: string;
  source_url: string | null;
  description: string;
  api_state: 'active' | 'paused' | 'upload_only';
  timezone: string;
  calendar_complete: boolean;
  next_due: string;
  expected_period_end: string;
  reminder_hours: number;
  snoozed_until: string | null;
}
export interface AccountSession {
  user: { id: string; name: string; email: string; is_admin: boolean };
  companies: Company[];
  company_id: string | null;
  csrf_token: string;
}
export interface Point {
  date: string;
  sales: number;
  units?: number | null;
  lower?: number;
  upper?: number;
}
export interface Product {
  product_id: string;
  product: string;
  sales: number;
  units: number | null;
  share: number | null;
  observed_days: number;
}
export interface Activity {
  id: string;
  kind: string;
  title: string;
  detail: string;
  created_at: string;
}
export interface Reminder {
  id: string;
  title: string;
  detail: string;
  created_at: string;
  read_at: string | null;
  action: string;
}
export interface Batch {
  id: string;
  name: string;
  status: string;
  source: string;
  received_at: string;
  processed_at: string | null;
  row_count?: number;
  columns?: string[];
  preview?: Record<string, unknown>[];
  options?: { mapping?: Record<string, string> };
  result: Record<string, unknown>;
}
export interface SecurityEvent {
  id: string;
  kind: string;
  occurred_at: string;
  payload: {
    source?: string;
    actor?: string;
    failed_attempts?: number;
    new_device?: number;
    location_difference?: number;
    login_hour?: number;
    characters?: number;
  };
  result: {
    status: string;
    is_anomaly?: boolean;
    anomaly_score?: number;
    risk_score?: number;
    is_phishing?: boolean;
  };
}
export interface Forecast {
  status: string;
  future: Point[];
  model?: string;
  mae?: number;
  baseline_mae?: number;
  prophet_mae?: number | null;
  interval_label?: string;
  message?: string;
  backtest?: { date: string; actual: number; predicted: number }[];
  trained_at?: string;
}
export interface Week {
  start: string;
  end: string;
  sales: number;
}
export interface Dashboard {
  company: Company;
  metrics: {
    sales_30d: number;
    previous_30d: number;
    sales_change_pct: number | null;
    expected_sales: number | null;
    units_30d: number | null;
    products: number;
    login_events: number;
    anomalies: number;
  };
  historical: Point[];
  forecast: Forecast;
  products: Product[];
  data_start: string | null;
  data_end: string | null;
  strongest_week: Week | null;
  quietest_week: Week | null;
  activity: Activity[];
  batches: Batch[];
  events: SecurityEvent[];
  reminders: Reminder[];
  phishing_status: string;
  insights: { kind: string; title: string; body: string; source: string }[];
  narration: { mode: string; external_processing: boolean };
  api_key: { prefix: string; created_at: string } | null;
}
export interface Validation {
  valid_rows: number;
  error_count: number;
  errors: { row: number; message: string }[];
  warnings: string[];
  preview: Record<string, unknown>[];
  date_start: string | null;
  date_end: string | null;
}
