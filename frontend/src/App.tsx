import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  Bell,
  ChartNoAxesCombined,
  Check,
  ChevronDown,
  CircleHelp,
  Command,
  Database,
  ExternalLink,
  FlaskConical,
  FolderInput,
  LayoutDashboard,
  Lightbulb,
  Menu,
  LogOut,
  Users,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  X,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { api, shortDate } from './api';
import { Badge, Dialog, Empty, ErrorBox, Spinner } from './components';
import { ActivityPage, DataHub, Insights, ModelLab, Overview, Sales, Security } from './pages';
import UploadWizard from './UploadWizard';
import Team from './Team';
import type { AccountSession, Batch, Company, Dashboard, Page } from './types';

const navigation: { id: Page; label: string; icon: LucideIcon; sub: string }[] = [
  {
    id: 'overview',
    label: 'Overview',
    icon: LayoutDashboard,
    sub: 'The whole picture, without the noise.',
  },
  {
    id: 'data',
    label: 'Data Hub',
    icon: FolderInput,
    sub: 'Connect your sources. Keep your context.',
  },
  {
    id: 'sales',
    label: 'Sales Outlook',
    icon: ChartNoAxesCombined,
    sub: 'A considered view of what comes next.',
  },
  {
    id: 'security',
    label: 'Security',
    icon: ShieldCheck,
    sub: 'Read the signals. Understand the context.',
  },
  {
    id: 'insights',
    label: 'Insights',
    icon: Lightbulb,
    sub: 'Evidence you can trace. Observations you can use.',
  },
  {
    id: 'activity',
    label: 'Activity',
    icon: Activity,
    sub: 'A clear record of what changed, and when.',
  },
  {
    id: 'lab',
    label: 'Model Lab',
    icon: FlaskConical,
    sub: 'Inspect the experimental models, separately.',
  },
];
function initialPage(): Page {
  return navigation.find((item) => item.id === location.hash.slice(1))?.id || 'overview';
}

export default function App({
  session,
  onSession,
  onLogout,
}: {
  session: AccountSession;
  onSession: (value: AccountSession) => void;
  onLogout: () => Promise<void>;
}) {
  const [team, setTeam] = useState(false);
  const initials = session.user.name
    .split(' ')
    .slice(0, 2)
    .map((word) => word[0])
    .join('')
    .toUpperCase();
  const [page, setPage] = useState<Page>(initialPage),
    [companies, setCompanies] = useState<Company[]>([]),
    [data, setData] = useState<Dashboard | null>(null);
  const [horizon, setHorizon] = useState(30),
    [busy, setBusy] = useState(true),
    [error, setError] = useState(''),
    [notice, setNotice] = useState('');
  const [workspaceMenu, setWorkspaceMenu] = useState(false),
    [sidebar, setSidebar] = useState(false),
    [notifications, setNotifications] = useState(false),
    [search, setSearch] = useState(false),
    [query, setQuery] = useState('');
  const [uploading, setUploading] = useState(false),
    [batch, setBatch] = useState<Batch | undefined>(),
    [help, setHelp] = useState(false),
    [creating, setCreating] = useState(false),
    [name, setName] = useState(''),
    [currency, setCurrency] = useState('GBP');
  const sequence = useRef(0),
    activeCompany = useRef('');
  const menuRef = useRef<HTMLDivElement>(null);
  const toast = useCallback((message: string) => setNotice(message), []);
  const go = useCallback((value: Page) => {
    location.hash = value;
    setPage(value);
    setSidebar(false);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, []);
  const load = useCallback(async (id: string, days: number, select = false) => {
    const seq = ++sequence.current;
    setBusy(true);
    setError('');
    try {
      if (select) {
        const account = await api<AccountSession>('/auth/workspace', {
          method: 'POST',
          body: JSON.stringify({ company_id: id }),
        });
        setCompanies(account.companies);
        onSession(account);
      }
      const result = await api<Dashboard>(`/dashboard?horizon=${days}`);
      if (seq === sequence.current) {
        setData(result);
        activeCompany.current = id;
      }
    } catch (err) {
      if (seq === sequence.current) setError((err as Error).message);
    } finally {
      if (seq === sequence.current) setBusy(false);
    }
  }, []);
  useEffect(() => {
    setCompanies(session.companies);
    const selected =
      session.companies.find((c) => c.id === session.company_id) || session.companies[0];
    if (selected) void load(selected.id, 30, selected.id !== session.company_id);
    else setBusy(false);
  }, [load]);
  useEffect(() => {
    const listener = () => setPage(initialPage());
    window.addEventListener('hashchange', listener);
    const keyboard = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setSearch((value) => !value);
      }
    };
    window.addEventListener('keydown', keyboard);
    const outside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node))
        setWorkspaceMenu(false);
    };
    document.addEventListener('mousedown', outside);
    return () => {
      window.removeEventListener('hashchange', listener);
      window.removeEventListener('keydown', keyboard);
      document.removeEventListener('mousedown', outside);
    };
  }, []);
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(''), 4500);
    return () => clearTimeout(timer);
  }, [notice]);
  useEffect(() => {
    if (!data) return;
    const timer = setInterval(
      async () => {
        if (document.visibilityState !== 'visible' || busy) return;
        try {
          const result = await api<Dashboard>(`/dashboard?horizon=${horizon}`);
          if (result.company.id === activeCompany.current) setData(result);
        } catch {
          /* Explicit refresh surfaces connection errors; preserve the last successful view. */
        }
      },
      data.batches.some((item) => item.status === 'processing') ? 2000 : 15000,
    );
    return () => clearInterval(timer);
  }, [data?.company.id, data?.batches.some((item) => item.status === 'processing'), horizon, busy]);
  async function refresh() {
    if (activeCompany.current) await load(activeCompany.current, horizon);
  }
  async function switchWorkspace(id: string) {
    setWorkspaceMenu(false);
    await load(id, horizon, true);
  }
  async function newWorkspace(id: string) {
    const result = await api<AccountSession>('/auth/me');
    setCompanies(result.companies);
    onSession(result);
    await load(id, horizon, true);
  }
  function openUpload(value?: Batch) {
    setBatch(value);
    setUploading(true);
  }
  async function create() {
    setBusy(true);
    setError('');
    try {
      const result = await api<Company>('/companies', {
        method: 'POST',
        body: JSON.stringify({ name, currency }),
      });
      await newWorkspace(result.id);
      setCreating(false);
      setName('');
      toast('Workspace created');
      go('data');
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }
  const allowedPage = page === 'lab' && !session.user.is_admin ? 'overview' : page;
  const selected = navigation.find((item) => item.id === allowedPage)!;
  const unread = data?.reminders.filter((item) => !item.read_at).length || 0;
  const shared = data ? { data, go, upload: openUpload, refresh, toast, horizon } : null;
  const views = {
    overview: Overview,
    data: DataHub,
    sales: Sales,
    security: Security,
    insights: Insights,
    activity: ActivityPage,
    lab: ModelLab,
  };
  const View = views[allowedPage];
  return (
    <div className="app-shell">
      {sidebar && (
        <button
          className="sidebar-scrim"
          aria-label="Close navigation"
          onClick={() => setSidebar(false)}
        />
      )}
      <aside className={`sidebar ${sidebar ? 'open' : ''}`}>
        <a href="#overview" className="brand" onClick={() => go('overview')}>
          <span className="brand-mark">
            <i />
            <i />
          </span>
          <span>
            Fore<span>Sight</span>
            <small>BUSINESS INTELLIGENCE</small>
          </span>
        </a>
        <div className="workspace-container" ref={menuRef}>
          <button
            className="workspace-button"
            aria-expanded={workspaceMenu}
            title={session.user.is_admin ? 'Open admin company switcher' : 'Open company switcher'}
            onClick={() => setWorkspaceMenu(!workspaceMenu)}
            disabled={busy}
          >
            <span className="workspace-avatar">{data?.company.initials || 'FS'}</span>
            <span>
              <strong>{data?.company.name || 'Your workspace'}</strong>
              <small>{session.user.is_admin ? 'Administrator view' : 'Company workspace'}</small>
            </span>
            <ChevronDown size={14} />
          </button>
          {workspaceMenu && (
            <div className="workspace-menu">
              <p className="eyebrow">
                {session.user.is_admin ? 'ADMIN / COMPANY SWITCHER' : 'YOUR COMPANIES'}
              </p>
              {companies.map((company) => (
                <button key={company.id} onClick={() => switchWorkspace(company.id)}>
                  <span className="small-avatar">{company.initials}</span>
                  <span>
                    <strong>{company.name}</strong>
                    <small>
                      {company.segment
                        ? `UCI · ${company.segment}`
                        : company.currency + ' · Upload workspace'}
                    </small>
                  </span>
                  {data?.company.id === company.id && <Check size={14} />}
                </button>
              ))}
              <button
                className="new-workspace"
                onClick={() => {
                  setWorkspaceMenu(false);
                  setCreating(true);
                }}
              >
                <Plus size={15} />
                New upload workspace
              </button>
            </div>
          )}
        </div>
        <div className="nav-label">WORKSPACE</div>
        <nav aria-label="Main navigation">
          {navigation.slice(0, 6).map(({ id, label, icon: Icon }) => (
            <a
              key={id}
              href={`#${id}`}
              className={`nav-item ${page === id ? 'active' : ''}`}
              aria-label={label}
              aria-current={page === id ? 'page' : undefined}
              onClick={() => go(id)}
            >
              <Icon size={18} strokeWidth={1.55} />
              <span>{label}</span>
              {id === 'activity' && unread > 0 && <span className="nav-count">{unread}</span>}
            </a>
          ))}
        </nav>
        <div className="sidebar-secondary">
          <div className="nav-label">EXPLORE</div>
          {session.user.is_admin && (
            <a
              href="#lab"
              className={`nav-item ${page === 'lab' ? 'active' : ''}`}
              onClick={() => go('lab')}
            >
              <FlaskConical size={18} strokeWidth={1.5} />
              Model Lab
              <span className="experimental-dot" />
            </a>
          )}
        </div>
        <div className="sidebar-bottom">
          <div className="local-status">
            <span className="tiny-dot sage" />
            <span>Local demonstration</span>
            <span className="mono">V1.0</span>
          </div>
          <div className="workspace-owner">
            <span className="owner-avatar">{initials}</span>
            <span>
              <strong>{session.user.name}</strong>
              <small>
                {session.user.is_admin
                  ? 'Administrator'
                  : data?.company.role === 'owner'
                    ? 'Company owner'
                    : 'Company member'}
              </small>
            </span>
            <button
              className="icon-button"
              aria-label="About this demonstration"
              onClick={() => setHelp(true)}
            >
              <CircleHelp size={16} />
            </button>
          </div>
          {data && data.company.role !== 'member' && (
            <div className="account-actions">
              <button onClick={() => setTeam(true)}>
                <Users size={14} />
                Manage team
              </button>
            </div>
          )}
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="icon-button mobile-menu"
              aria-label="Open navigation"
              onClick={() => setSidebar(true)}
            >
              <Menu size={19} />
            </button>
            <span>Workspace</span>
            <span className="breadcrumb-slash">/</span>
            <strong>{selected.label}</strong>
          </div>
          <div className="top-actions">
            <button className="search-button" title="Find anything" onClick={() => setSearch(true)}>
              <Search size={15} />
              <span>Find anything</span>
              <kbd>
                <Command size={10} /> K
              </kbd>
            </button>
            <div className="header-divider" />
            <button
              className="icon-button notification-button"
              aria-label={`Notifications${unread ? `, ${unread} unread` : ''}`}
              onClick={() => setNotifications(true)}
            >
              <Bell size={18} strokeWidth={1.6} />
              {unread > 0 && <i />}
            </button>
            <span className="top-avatar" title={session.user.email}>
              {initials}
            </span>
            <button
              className="icon-button"
              aria-label="Sign out"
              onClick={() => {
                void onLogout().catch((err) => toast(err.message));
              }}
            >
              <LogOut size={17} />
            </button>
          </div>
        </header>
        <main id="main-content">
          <div className="page-heading">
            <div>
              <p className="eyebrow">
                {data?.company.name.toUpperCase() || 'FORESIGHT'} <span>/</span> BUSINESS
                INTELLIGENCE
              </p>
              <h1>
                {selected.label}
                <span className="heading-period">.</span>
              </h1>
              <p className="page-description">{selected.sub}</p>
            </div>
            <div className="heading-actions">
              <a
                href="/api/export/sales.csv"
                className="button secondary"
                aria-label="Export data — sales observations"
              >
                <ArrowDownToLine size={15} />
                Export data
              </a>
              <button className="button primary" onClick={() => openUpload()} disabled={!data}>
                <Plus size={16} />
                Add data
              </button>
            </div>
          </div>
          {data && (
            <div className="context-bar">
              <div>
                <span
                  className={`tiny-dot ${data.company.source_kind === 'public' ? 'brass' : 'sage'}`}
                />
                <span>
                  {data.company.source_kind === 'public' ? 'PUBLIC DATASET' : 'UPLOAD WORKSPACE'}
                </span>
                <b>
                  {data.company.segment
                    ? `${data.company.segment} · 12-product sample`
                    : data.company.name}
                </b>
                <span className="context-divider" />
                <span>
                  As of <strong>{shortDate(data.data_end, true)}</strong>
                </span>
              </div>
              <div className="range-controls">
                {(page === 'overview' || page === 'sales') && (
                  <>
                    <span className="range-caption">Outlook</span>
                    {[30, 60, 90].map((days) => (
                      <button
                        key={days}
                        className={horizon === days ? 'selected' : ''}
                        disabled={busy}
                        onClick={() => {
                          setHorizon(days);
                          void load(data.company.id, days);
                        }}
                      >
                        {days}D
                      </button>
                    ))}
                  </>
                )}
                <button
                  className={`refresh-button ${busy ? 'is-refreshing' : ''}`}
                  aria-label="Refresh workspace"
                  disabled={busy}
                  onClick={refresh}
                >
                  <RefreshCw size={14} />
                </button>
              </div>
            </div>
          )}
          {error && (
            <div className="page-error">
              <ErrorBox>
                {error}
                <button className="text-link" onClick={refresh}>
                  Try again
                  <RefreshCw size={12} />
                </button>
              </ErrorBox>
            </div>
          )}
          {!data ? (
            busy ? (
              <div className="page-loading">
                <div className="loading-monogram">
                  <span className="brand-mark">
                    <i />
                    <i />
                  </span>
                </div>
                <h2>Bringing your business into focus.</h2>
                <Spinner label="Loading workspace data" />
              </div>
            ) : (
              <Empty
                icon={Database}
                title="The workspace is unavailable"
                detail="Check that the ForeSight backend is running, then reload this page."
                action={
                  <button className="button secondary" onClick={() => location.reload()}>
                    <RefreshCw size={15} />
                    Reload
                  </button>
                }
              />
            )
          ) : (
            <div key={page + data.company.id} className={`page-content page-${page}`}>
              {shared && <View {...shared} />}
            </div>
          )}
          <footer className="main-footer">
            <span className="footer-wordmark">ForeSight</span>
            <span>
              {data?.company.source_kind === 'public'
                ? 'Historical public data · fictional sample workspace'
                : 'Local company upload workspace'}
              <i />
              Evidence before assumptions.
            </span>
            <button onClick={() => setHelp(true)}>
              Source notes <ExternalLink size={11} />
            </button>
          </footer>
        </main>
      </div>
      {notice && (
        <div className="toast" role="status">
          <span>
            <Check size={14} />
          </span>
          {notice}
          <button aria-label="Dismiss notification" onClick={() => setNotice('')}>
            <X size={14} />
          </button>
        </div>
      )}
      {uploading && data && (
        <UploadWizard
          company={data.company}
          existing={batch}
          onClose={() => setUploading(false)}
          onWorkspace={newWorkspace}
          onProcessed={() => {
            setUploading(false);
            void refresh();
            go('data');
            toast('Data submitted for processing');
          }}
        />
      )}
      {search && (
        <Dialog
          title="Find your next view"
          eyebrow="WORKSPACE SEARCH"
          onClose={() => {
            setSearch(false);
            setQuery('');
          }}
        >
          <div className="dialog-body search-dialog">
            <div className="search-input">
              <Search size={18} />
              <input
                autoFocus
                placeholder="Search pages or products…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                aria-label="Search workspace"
              />
            </div>
            <p className="eyebrow">PAGES</p>
            {navigation
              .filter((item) => item.id !== 'lab' || session.user.is_admin)
              .filter((item) =>
                `${item.label} ${item.sub}`.toLowerCase().includes(query.toLowerCase()),
              )
              .map(({ id, icon: Icon, label }) => (
                <button
                  className="search-result"
                  key={id}
                  onClick={() => {
                    go(id);
                    setSearch(false);
                    setQuery('');
                  }}
                >
                  <Icon size={17} />
                  <span>{label}</span>
                  <ArrowRight size={15} />
                </button>
              ))}
            {query && (
              <>
                <p className="eyebrow">PRODUCTS IN THIS WORKSPACE</p>
                {data?.products
                  .filter((item) => item.product.toLowerCase().includes(query.toLowerCase()))
                  .slice(0, 5)
                  .map((product) => (
                    <button
                      className="search-result"
                      key={product.product_id}
                      onClick={() => {
                        go('sales');
                        setSearch(false);
                        setQuery('');
                      }}
                    >
                      <Database size={16} />
                      <span>{product.product.toLowerCase()}</span>
                      <ArrowRight size={15} />
                    </button>
                  ))}
              </>
            )}
          </div>
        </Dialog>
      )}
      {notifications && (
        <Dialog
          title="Your attention, well placed"
          eyebrow="WORKSPACE NOTIFICATIONS"
          onClose={() => setNotifications(false)}
        >
          <div className="dialog-body">
            {unread ? (
              <p className="body-small">
                {unread} unread data reminders. Your reporting schedule controls when these appear.
              </p>
            ) : (
              <p className="body-small">No unread reminders for this workspace.</p>
            )}
            {data?.reminders.map((reminder) => (
              <button
                className="notification-item"
                key={reminder.id}
                onClick={async () => {
                  await api(`/reminders/${reminder.id}/read`, { method: 'POST' });
                  await refresh();
                  setNotifications(false);
                  go('activity');
                }}
              >
                <Bell size={17} />
                <span>
                  <strong>{reminder.title}</strong>
                  <small>{reminder.detail}</small>
                </span>
                <ArrowRight size={16} />
              </button>
            ))}
            <button
              className="button secondary"
              onClick={() => {
                setNotifications(false);
                go('activity');
              }}
            >
              View activity <ArrowRight size={14} />
            </button>
          </div>
        </Dialog>
      )}
      {creating && (
        <Dialog
          title="A workspace for your own data"
          eyebrow="NEW LOCAL WORKSPACE"
          onClose={() => setCreating(false)}
        >
          <div className="dialog-body">
            {error && <ErrorBox>{error}</ErrorBox>}
            <p className="body-small">
              Keep your observations separate from the public samples. Review field mappings after
              your first upload.
            </p>
            <div className="form-stack">
              <label>
                Workspace name
                <input
                  autoFocus
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Juniper Studio"
                  maxLength={50}
                />
              </label>
              <label>
                Reporting currency
                <select value={currency} onChange={(e) => setCurrency(e.target.value)}>
                  {['GBP', 'USD', 'EUR', 'INR', 'AUD', 'CAD', 'JPY'].map((c) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
              </label>
            </div>
          </div>
          <div className="dialog-footer">
            <button className="button ghost" onClick={() => setCreating(false)}>
              Cancel
            </button>
            <button
              className="button primary"
              disabled={busy || name.trim().length < 2}
              onClick={create}
            >
              {busy ? (
                <Spinner />
              ) : (
                <>
                  Create workspace
                  <ArrowRight size={14} />
                </>
              )}
            </button>
          </div>
        </Dialog>
      )}
      {team && data && (
        <Team
          companyName={data.company.name}
          userId={session.user.id}
          onClose={() => setTeam(false)}
        />
      )}
      {help && (
        <Dialog
          title="A clear view of the evidence"
          eyebrow="SOURCES & METHODOLOGY"
          wide
          onClose={() => setHelp(false)}
        >
          <div className="dialog-body methodology">
            <Badge tone="brass">College demonstration · local only</Badge>
            <h3>One public retailer. Three distinct sample workspaces.</h3>
            <p>
              Aster Trading, Maison Supply, and Nordhaus are fictional workspaces representing the
              United Kingdom, France, and Germany customer-country segments of the UCI Online Retail
              dataset. Each uses twelve selected merchandise SKUs, with signed cancellations and
              returns retained. Postage and manual adjustment codes are excluded. These are not
              three independently observed companies.
            </p>
            <p>
              The historical period ends in December 2011 and uses GBP. The forecasting cutoff stays
              attached to the actual source dates. Upload workspaces store their own records
              separately.
            </p>
            <h3>Forecasting with a baseline</h3>
            <p>
              The last 28 daily observations are held out. Prophet is selected only when its mean
              absolute error is lower than a weekly seasonal baseline. Forecast ranges are
              indicative. Product selection is fixed using the complete public history, so
              evaluation is conditional on that selected series.
            </p>
            <h3>Models and data boundaries</h3>
            <p>
              Preloaded login events are synthetic examples scored by the original Isolation Forest.
              Phishing analysis requires the contributor's trained artifact. The Model Lab contains
              a separate synthetic/prototype XGBoost experiment. No global business-failure
              probability is inferred from these unrelated datasets.
            </p>
            <h3>Your data stays here</h3>
            <p>
              ForeSight uses a local SQLite store, password-protected accounts, revocable sessions,
              and company-scoped ingestion keys. Owners manage company membership; administrators
              alone can browse all companies and the Model Lab. External LLM processing is disabled.
              All application fonts are bundled locally.
            </p>
            <a
              className="text-link"
              href="https://doi.org/10.24432/C5BW33"
              target="_blank"
              rel="noreferrer"
            >
              Daqing Chen · Online Retail · UCI · CC BY 4.0
              <ExternalLink size={13} />
            </a>
          </div>
        </Dialog>
      )}
    </div>
  );
}
