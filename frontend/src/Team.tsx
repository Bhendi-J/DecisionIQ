import { useEffect, useState } from 'react';
import { Plus, Trash2, Users } from 'lucide-react';
import { api } from './api';
import { Dialog, ErrorBox, Spinner } from './components';

type Member = { id: string; name: string; email: string; role: 'owner' | 'member' };
export default function Team({
  companyName,
  userId,
  onClose,
}: {
  companyName: string;
  userId: string;
  onClose: () => void;
}) {
  const [members, setMembers] = useState<Member[]>([]);
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('member');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  async function load() {
    setMembers(await api<Member[]>('/auth/members'));
  }
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, []);
  async function add(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await api('/auth/members', { method: 'POST', body: JSON.stringify({ email, role }) });
      setEmail('');
      await load();
      setNotice('Company access granted. Your teammate can now select this workspace.');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function remove(member: Member) {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await api(`/auth/members/${member.id}`, { method: 'DELETE' });
      await load();
      setNotice('Company access removed.');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      title="The right people, in context"
      eyebrow={`${companyName.toUpperCase()} / TEAM ACCESS`}
      onClose={onClose}
      wide
    >
      <div className="dialog-body team-dialog">
        {error && <ErrorBox>{error}</ErrorBox>}
        {notice && (
          <p className="success-box" role="status">
            {notice}
          </p>
        )}
        <p className="body-small">
          Add a teammate who already has a ForeSight account. Owners manage settings, credentials,
          and access. Members can upload and analyze company data.
        </p>
        <form className="team-add" onSubmit={add}>
          <label>
            Teammate email
            <input
              type="email"
              autoComplete="off"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
          <label>
            Company role
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="member">Member</option>
              <option value="owner">Owner</option>
            </select>
          </label>
          <button className="button primary" disabled={busy}>
            {busy ? (
              <Spinner />
            ) : (
              <>
                <Plus size={15} />
                Grant access
              </>
            )}
          </button>
        </form>
        <div className="team-list">
          {members.map((member) => (
            <div className="team-member" key={member.id}>
              <Users size={17} />
              <span>
                <strong>
                  {member.name}
                  {member.id === userId ? ' (you)' : ''}
                </strong>
                <small>{member.email}</small>
              </span>
              <span className="team-role">{member.role}</span>
              <button
                className="icon-button"
                aria-label={`Remove access for ${member.email}`}
                disabled={busy || member.id === userId}
                onClick={() => remove(member)}
              >
                <Trash2 size={15} />
              </button>
            </div>
          ))}
        </div>
        <p className="body-small">
          Each company keeps at least one owner. No email invitations are sent by this local
          application.
        </p>
      </div>
    </Dialog>
  );
}
