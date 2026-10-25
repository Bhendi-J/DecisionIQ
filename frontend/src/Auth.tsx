import { useEffect, useState } from 'react';
import { ArrowRight, Eye, EyeOff, LockKeyhole, ShieldCheck } from 'lucide-react';
import { api, setCsrfToken } from './api';
import { ErrorBox, Spinner } from './components';
import App from './App';
import type { AccountSession } from './types';

export default function AuthGate() {
  const [session, setSession] = useState<AccountSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [connectionError, setConnectionError] = useState('');
  function authenticated(value: AccountSession) {
    setCsrfToken(value.csrf_token);
    setSession(value);
    setLoading(false);
  }
  useEffect(() => {
    let active = true;
    const unauthorized = () => {
      setCsrfToken('');
      setSession(null);
      setLoading(false);
    };
    window.addEventListener('foresight:unauthorized', unauthorized);
    api<AccountSession>('/auth/me')
      .then((value) => {
        if (active) authenticated(value);
      })
      .catch((error) => {
        if (active && error.message !== 'Sign in to your ForeSight account.')
          setConnectionError(error.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
      window.removeEventListener('foresight:unauthorized', unauthorized);
    };
  }, []);
  async function logout() {
    await api('/auth/logout', { method: 'POST' });
    setCsrfToken('');
    setSession(null);
    location.hash = 'overview';
  }
  if (loading)
    return (
      <div className="auth-loading" role="status">
        <Spinner />
        Opening ForeSight…
      </div>
    );
  if (session)
    return (
      <App key={session.user.id} session={session} onSession={authenticated} onLogout={logout} />
    );
  return <AuthPage onAuthenticated={authenticated} connectionError={connectionError} />;
}

function AuthPage({
  onAuthenticated,
  connectionError,
}: {
  onAuthenticated: (session: AccountSession) => void;
  connectionError: string;
}) {
  const [registering, setRegistering] = useState(false);
  const [visible, setVisible] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [company, setCompany] = useState('');
  const [currency, setCurrency] = useState('GBP');
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const value = await api<AccountSession>(registering ? '/auth/register' : '/auth/login', {
        method: 'POST',
        body: JSON.stringify({
          email,
          password,
          ...(registering
            ? {
                name,
                company_name: company,
                currency,
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
              }
            : {}),
        }),
      });
      setPassword('');
      onAuthenticated(value);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function changeMode() {
    setRegistering(!registering);
    setError('');
    setPassword('');
  }
  return (
    <main className="auth-shell">
      <section className="auth-story" aria-label="About ForeSight">
        <a className="brand" href="#overview">
          <span className="brand-mark">
            <i />
            <i />
          </span>
          <span>
            Fore<span>Sight</span>
            <small>BUSINESS INTELLIGENCE</small>
          </span>
        </a>
        <div className="auth-story-copy">
          <p className="eyebrow">A CLEARER PERSPECTIVE</p>
          <h1>
            Clarity starts
            <br />
            with context<span>.</span>
          </h1>
          <p>
            Your sales, your signals, your next move. Bring the evidence into one considered view.
          </p>
          <div className="auth-orbit" aria-hidden="true">
            <div />
            <div />
            <div />
            <span>
              F<span>S</span>
            </span>
            <i />
            <b />
          </div>
        </div>
        <div className="auth-story-footer">
          <span className="tiny-dot brass" />
          Evidence before assumptions.<span>ForeSight / 01</span>
        </div>
      </section>
      <section className="auth-form-side" aria-labelledby="auth-title">
        <div className="auth-form-content">
          <p className="eyebrow">
            {registering ? 'YOUR COMPANY, IN FOCUS' : 'YOUR WORKSPACE AWAITS'}
          </p>
          <h2 id="auth-title">{registering ? 'Create your account.' : 'Welcome back.'}</h2>
          <p className="auth-intro">
            {registering
              ? 'Start with a private workspace for your company’s data.'
              : 'Sign in to the companies and insights you have access to.'}
          </p>
          {(error || connectionError) && <ErrorBox>{error || connectionError}</ErrorBox>}
          <form onSubmit={submit} className="form-stack auth-form">
            {registering && (
              <label>
                Your name
                <input
                  autoComplete="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  minLength={2}
                  maxLength={80}
                  required
                />
              </label>
            )}
            <label>
              Email address
              <input
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                maxLength={254}
                required
              />
            </label>
            <label>
              Password
              <div className="password-field">
                <input
                  type={visible ? 'text' : 'password'}
                  autoComplete={registering ? 'new-password' : 'current-password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  minLength={registering ? 12 : 1}
                  maxLength={128}
                  required
                  aria-describedby={registering ? 'password-help' : undefined}
                />
                <button
                  type="button"
                  className="icon-button"
                  aria-label={visible ? 'Hide password' : 'Show password'}
                  onClick={() => setVisible(!visible)}
                >
                  {visible ? <EyeOff size={17} /> : <Eye size={17} />}
                </button>
              </div>
            </label>
            {registering && (
              <>
                <small className="auth-password-help" id="password-help">
                  Use 12–128 characters. A long, unique passphrase works well.
                </small>
                <div className="auth-company-fields">
                  <label>
                    Company name
                    <input
                      autoComplete="organization"
                      value={company}
                      onChange={(e) => setCompany(e.target.value)}
                      minLength={2}
                      maxLength={50}
                      required
                    />
                  </label>
                  <label>
                    Currency
                    <select value={currency} onChange={(e) => setCurrency(e.target.value)}>
                      {['GBP', 'USD', 'EUR', 'INR', 'AUD', 'CAD', 'JPY'].map((c) => (
                        <option key={c}>{c}</option>
                      ))}
                    </select>
                  </label>
                </div>
              </>
            )}
            <button className="button primary auth-submit" type="submit" disabled={busy}>
              {busy ? (
                <>
                  <Spinner />
                  {registering ? 'Creating your workspace…' : 'Signing in…'}
                </>
              ) : (
                <>
                  {registering ? 'Create account' : 'Sign in'}
                  <ArrowRight size={16} />
                </>
              )}
            </button>
          </form>
          <p className="auth-switch">
            {registering ? 'Already have an account?' : 'New to ForeSight?'}{' '}
            <button type="button" onClick={changeMode} disabled={busy}>
              {registering ? 'Sign in instead' : 'Create an account'}
              <ArrowRight size={12} />
            </button>
          </p>
          <div className="auth-trust">
            <LockKeyhole size={15} />
            <span>Private workspace access. External LLM processing is disabled.</span>
          </div>
        </div>
        <footer className="auth-form-footer">
          <ShieldCheck size={14} />
          <span>Account access is separate from login-event analysis.</span>
        </footer>
      </section>
    </main>
  );
}
