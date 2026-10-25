let csrfToken = '';
export function setCsrfToken(value: string) {
  csrfToken = value;
}
export function csrfHeaders(): Record<string, string> {
  return csrfToken ? { 'X-CSRF-Token': csrfToken } : {};
}
export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch('/api' + path, {
    ...options,
    credentials: 'same-origin',
    headers: {
      ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...csrfHeaders(),
      ...options.headers,
    },
  });
  if (!response.ok) {
    if (response.status === 401) window.dispatchEvent(new Event('foresight:unauthorized'));
    const error = await response
      .json()
      .catch(() => ({ detail: 'The server could not complete this request.' }));
    const detail = error.detail;
    throw new Error(
      typeof detail === 'string'
        ? detail
        : detail?.message ||
            detail?.errors?.[0]?.message ||
            (Array.isArray(detail)
              ? detail.map((item: { msg: string }) => item.msg).join('; ')
              : 'Check your input and try again.'),
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
export function money(value: number | null | undefined, currency = 'GBP', compact = false) {
  if (value == null) return '—';
  return new Intl.NumberFormat('en-GB', {
    style: 'currency',
    currency,
    notation: compact ? 'compact' : 'standard',
    maximumFractionDigits: compact ? 1 : 0,
  }).format(value);
}
export function number(value: number | null | undefined, compact = false) {
  return value == null
    ? '—'
    : new Intl.NumberFormat('en-GB', {
        notation: compact ? 'compact' : 'standard',
        maximumFractionDigits: 0,
      }).format(value);
}
export function shortDate(value: string | null | undefined, year = false) {
  if (!value) return 'No history';
  return new Date(value.slice(0, 10) + 'T12:00:00Z').toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    ...(year ? { year: 'numeric' } : {}),
    timeZone: 'UTC',
  });
}
export function time(value: string) {
  return new Date(value).toLocaleString('en-GB', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Asia/Kolkata',
  });
}
export function download(name: string, content: string, type = 'text/plain') {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
