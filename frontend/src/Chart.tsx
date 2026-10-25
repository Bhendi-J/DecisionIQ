import { useMemo, useState } from 'react';
import { money, shortDate } from './api';
import type { Point } from './types';

export default function Chart({
  history,
  future,
  currency,
  backtest = false,
}: {
  history: Point[];
  future: Point[];
  currency: string;
  backtest?: boolean;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const chart = useMemo(() => {
    const actual = history.slice(-90),
      predicted = future;
    const all = [...actual, ...predicted];
    const width = 1000,
      height = 280,
      left = 64,
      right = 18,
      top = 24,
      bottom = 38;
    const max = Math.max(1, ...all.map((p) => Math.max(p.sales, p.upper ?? p.sales))) * 1.12;
    const min = Math.min(0, ...all.map((p) => Math.min(p.sales, p.lower ?? p.sales)));
    const x = (index: number) =>
      left + (index / Math.max(1, all.length - 1)) * (width - left - right);
    const y = (value: number) => top + ((max - value) / (max - min)) * (height - top - bottom);
    const path = (points: Point[], start = 0, field: 'sales' | 'lower' | 'upper' = 'sales') =>
      points
        .map(
          (p, i) =>
            `${i ? 'L' : 'M'}${x(i + start).toFixed(2)},${y(p[field] ?? p.sales).toFixed(2)}`,
        )
        .join(' ');
    const band = predicted.length
      ? path(predicted, actual.length, 'upper') +
        ' ' +
        [...predicted]
          .reverse()
          .map((p, i) => `L${x(all.length - 1 - i)},${y(p.lower ?? p.sales)}`)
          .join(' ') +
        ' Z'
      : '';
    return {
      actual,
      predicted,
      all,
      width,
      height,
      max,
      min,
      x,
      y,
      path,
      band,
      left,
      right,
      top,
      bottom,
    };
  }, [history, future]);
  if (!chart.all.length)
    return (
      <div className="chart-empty">
        <span className="empty-orbit" />
        Your sales history will appear here after processing.
      </div>
    );
  const { all, actual, predicted, x, y } = chart;
  const hovered = hover == null ? null : all[hover];
  return (
    <div className="chart-wrap">
      <svg
        viewBox="0 0 1000 280"
        role="img"
        aria-label={`Recorded and forecast sales in ${currency}. ${actual.length} historical days and ${predicted.length} forecast days.`}
        onMouseLeave={() => setHover(null)}
        onMouseMove={(event) => {
          const rect = event.currentTarget.getBoundingClientRect();
          const position = ((event.clientX - rect.left) / rect.width) * 1000;
          setHover(
            Math.max(
              0,
              Math.min(
                all.length - 1,
                Math.round(((position - 64) / (1000 - 64 - 18)) * (all.length - 1)),
              ),
            ),
          );
        }}
      >
        <defs>
          <linearGradient id="salesFill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#cbbb96" stopOpacity=".09" />
            <stop offset="100%" stopColor="#cbbb96" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0, 1, 2, 3, 4].map((index) => {
          const value = chart.min + ((chart.max - chart.min) / 4) * index;
          return (
            <g key={index}>
              <line x1="64" x2="982" y1={y(value)} y2={y(value)} className="chart-grid" />
              <text x="50" y={y(value) + 4} textAnchor="end" className="axis-text">
                {money(value, currency, true)}
              </text>
            </g>
          );
        })}
        {predicted.length > 0 && (
          <>
            <rect
              x={x(actual.length)}
              y="8"
              width={982 - x(actual.length)}
              height="234"
              fill="#cbbb96"
              opacity=".025"
            />
            <line
              x1={x(actual.length)}
              x2={x(actual.length)}
              y1="14"
              y2="242"
              stroke="#756b57"
              strokeDasharray="3 5"
            />
            <text x={Math.min(890, x(actual.length) + 13)} y="20" className="forecast-label">
              {backtest ? 'PREDICTED' : 'OUTLOOK'}
            </text>
            <path d={chart.band} fill="#cbbb96" opacity=".09" />
          </>
        )}
        {actual.length > 0 && (
          <path
            d={chart.path(actual) + ` L${x(actual.length - 1)},242 L64,242 Z`}
            fill="url(#salesFill)"
          />
        )}
        <path
          d={chart.path(actual)}
          fill="none"
          stroke="#b5b4aa"
          strokeWidth="1.7"
          strokeLinejoin="round"
        />
        {predicted.length > 0 && (
          <path
            d={chart.path(
              actual.length ? [actual[actual.length - 1], ...predicted] : predicted,
              Math.max(0, actual.length - 1),
            )}
            fill="none"
            stroke="#d2bd8b"
            strokeWidth="2"
            strokeLinejoin="round"
          />
        )}
        {[0, 1, 2, 3, 4].map((index) => {
          const idx = Math.round(((all.length - 1) * index) / 4);
          return (
            <text
              key={index}
              x={x(idx)}
              y="271"
              textAnchor={index === 0 ? 'start' : index === 4 ? 'end' : 'middle'}
              className="axis-text"
            >
              {shortDate(all[idx].date)}
            </text>
          );
        })}
        {hover != null && hovered && (
          <>
            <line
              x1={x(hover)}
              x2={x(hover)}
              y1="24"
              y2="242"
              stroke="#777"
              strokeDasharray="3 4"
            />
            <circle
              cx={x(hover)}
              cy={y(hovered.sales)}
              r="4"
              fill="#d8c79f"
              stroke="#171819"
              strokeWidth="2"
            />
          </>
        )}
      </svg>
      {hovered && hover != null && (
        <div
          className="chart-tooltip"
          style={{ left: `${Math.max(4, Math.min(73, x(hover) / 10))}%` }}
        >
          <span>{shortDate(hovered.date, true)}</span>
          <strong>{money(hovered.sales, currency)}</strong>
          <small>{hover >= actual.length ? 'Expected sales' : 'Recorded sales'}</small>
        </div>
      )}
    </div>
  );
}
