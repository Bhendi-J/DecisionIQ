import { useEffect, useRef } from 'react';
import type { ReactNode } from 'react';
import { ArrowUpRight, Check, LoaderCircle, X } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { money, number } from './api';
import type { Product } from './types';

export function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: string }) {
  return (
    <span className={`badge ${tone}`}>
      <i />
      {children}
    </span>
  );
}
export function Spinner({ label = 'Working' }: { label?: string }) {
  return (
    <span className="inline-loading">
      <LoaderCircle size={15} className="spin" />
      {label}
    </span>
  );
}
export function Panel({
  title,
  eyebrow,
  action,
  className = '',
  children,
}: {
  title: string;
  eyebrow?: string;
  action?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-heading">
        <div>
          {eyebrow && <p className="eyebrow">{eyebrow}</p>}
          <h2>{title}</h2>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
export function Empty({
  icon: Icon,
  title,
  detail,
  action,
}: {
  icon: LucideIcon;
  title: string;
  detail: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <span className="empty-icon">
        <Icon size={22} strokeWidth={1.3} />
      </span>
      <h3>{title}</h3>
      <p>{detail}</p>
      {action}
    </div>
  );
}
export function Dialog({
  title,
  eyebrow,
  children,
  onClose,
  wide = false,
}: {
  title: string;
  eyebrow?: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    dialog?.showModal();
    return () => {
      dialog?.close();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className={`dialog ${wide ? 'wide' : ''}`}
      aria-label={title}
      onCancel={onClose}
      onClick={(event) => {
        if (event.target === ref.current) onClose();
      }}
    >
      <div className="dialog-header">
        <div>
          {eyebrow && <p className="eyebrow">{eyebrow}</p>}
          <h2>{title}</h2>
        </div>
        <button className="icon-button" aria-label="Close dialog" onClick={onClose}>
          <X size={19} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
export function ErrorBox({ children }: { children: ReactNode }) {
  return (
    <div className="error-box" role="alert">
      {children}
    </div>
  );
}
export function Success({ children }: { children: ReactNode }) {
  return (
    <div className="success-box">
      <Check size={16} />
      {children}
    </div>
  );
}
export function ProductTable({
  products,
  currency,
  short = false,
}: {
  products: Product[];
  currency: string;
  short?: boolean;
}) {
  return (
    <div className="table-scroll">
      <table className="product-table">
        <thead>
          <tr>
            <th>Product</th>
            <th className="numeric">Sales value</th>
            <th className="numeric hide-small">Units</th>
            <th className="share-col">Share of sales</th>
          </tr>
        </thead>
        <tbody>
          {products.slice(0, short ? 4 : 12).map((p, index) => (
            <tr key={p.product_id}>
              <td>
                <div className="product-cell">
                  <span className={`product-avatar color-${index % 4}`}>
                    {p.product
                      .split(' ')
                      .slice(0, 2)
                      .map((s) => s[0])
                      .join('')}
                  </span>
                  <div>
                    <span className="product-name">{p.product.toLowerCase()}</span>
                    <small>{p.product_id}</small>
                  </div>
                </div>
              </td>
              <td className="numeric">{money(p.sales, currency)}</td>
              <td className="numeric hide-small muted">{number(p.units)}</td>
              <td>
                <div className="share-cell">
                  <span className="share-track">
                    <i style={{ width: `${Math.max(0, Math.min(100, (p.share || 0) * 100))}%` }} />
                  </span>
                  <span>{p.share == null ? '—' : (p.share * 100).toFixed(1) + '%'}</span>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function TextLink({ children, onClick }: { children: ReactNode; onClick: () => void }) {
  return (
    <button className="text-link" onClick={onClick}>
      {children}
      <ArrowUpRight size={14} />
    </button>
  );
}
