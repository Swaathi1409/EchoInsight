/**
 * AdminPanel: admin-only pages for audit logs, checklists, budget status, and cases.
 * Accessible from the sidebar when user role is admin or supervisor.
 */
import { useEffect, useState, useCallback } from 'react';
import { api, getToken } from '../api';
import {
  Shield, Activity, List, Link, ChevronDown, ChevronRight,
  RefreshCw, Plus, CheckCircle, XCircle, AlertTriangle
} from 'lucide-react';

function parseJwt(token) {
  try {
    const base64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    return JSON.parse(atob(base64));
  } catch { return {}; }
}

function getUserRole() {
  const tok = getToken();
  if (!tok) return null;
  return parseJwt(tok).role || null;
}

// ---------------------------------------------------------------------------
// Budget Status Card
// ---------------------------------------------------------------------------
function BudgetCard() {
  const [budget, setBudget] = useState(null);
  const [err, setErr] = useState('');
  useEffect(() => {
    api.getBudgetStatus().then(setBudget).catch(e => setErr(e.message));
  }, []);
  if (err) return <div className="card"><div className="error-banner">{err}</div></div>;
  if (!budget) return <div className="card"><div className="skeleton" style={{ height: 60 }} /></div>;
  const pct = budget.pct_used;
  const color = pct >= 90 ? 'var(--red)' : pct >= 70 ? 'var(--amber)' : 'var(--green)';
  return (
    <div className="card">
      <div className="card-header"><span className="card-title">Daily LLM Token Budget</span><span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{budget.date}</span></div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 10 }}>
        <div style={{ fontSize: 28, fontWeight: 800, color }}>{budget.pct_used.toFixed(1)}%</div>
        <div>
          <div style={{ fontSize: 13 }}>{budget.used.toLocaleString()} / {budget.limit.toLocaleString()} tokens</div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{budget.remaining.toLocaleString()} remaining</div>
        </div>
      </div>
      <div style={{ height: 8, background: 'var(--bg-secondary)', borderRadius: 4, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${Math.min(pct, 100)}%`, background: color, borderRadius: 4, transition: 'width 0.4s ease' }} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Audit Log
// ---------------------------------------------------------------------------
function AuditLogTable() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');
  useEffect(() => {
    const params = filter ? { action: filter } : {};
    api.getAuditLogs(params).then(data => { setLogs(data); setLoading(false); });
  }, [filter]);

  const actions = [...new Set(logs.map(l => l.action))].sort();

  return (
    <div className="card" style={{ padding: 0 }}>
      <div style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 10, borderBottom: '1px solid var(--border-subtle)' }}>
        <span className="card-title">Audit Log</span>
        <select value={filter} onChange={e => setFilter(e.target.value)}
          style={{ marginLeft: 'auto', fontSize: 12, background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: 4, padding: '4px 8px', color: 'var(--text-primary)' }}>
          <option value="">All actions</option>
          {actions.map(a => <option key={a} value={a}>{a}</option>)}
        </select>
      </div>
      {loading ? <div style={{ padding: 20 }}><div className="skeleton" style={{ height: 40 }} /></div> : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                {['Time', 'Action', 'Resource', 'Details'].map(h => (
                  <th key={h} style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-muted)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {logs.length === 0 ? (
                <tr><td colSpan={4} style={{ padding: 24, textAlign: 'center', color: 'var(--text-muted)' }}>No audit entries yet.</td></tr>
              ) : logs.map(l => (
                <tr key={l.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  <td style={{ padding: '8px 12px', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{new Date(l.created_at).toLocaleString()}</td>
                  <td style={{ padding: '8px 12px' }}><span className="badge badge-blue">{l.action}</span></td>
                  <td style={{ padding: '8px 12px', color: 'var(--text-secondary)' }}>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{l.resource_type} / </span>
                    <code style={{ fontSize: 11 }}>{l.resource_id.slice(0, 12)}</code>
                  </td>
                  <td style={{ padding: '8px 12px', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--text-muted)', fontSize: 11 }}>
                    {JSON.stringify(l.details)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Checklist Manager
// ---------------------------------------------------------------------------
function ChecklistManager() {
  const [checklists, setChecklists] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api.getChecklists().then(data => { setChecklists(data); setLoading(false); }).catch(() => setLoading(false));
  }, []);
  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">QA Checklists</span>
      </div>
      {loading ? <div className="skeleton" style={{ height: 40 }} /> : (
        checklists.length === 0 ? (
          <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>No checklist versions found. Policy YAML files go in backend/config/policy_*.yaml.</p>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr>
                {['Version', 'Name', 'Items', 'Active'].map(h => (
                  <th key={h} style={{ padding: '8px 0', textAlign: 'left', color: 'var(--text-muted)', fontSize: 11, fontWeight: 600, textTransform: 'uppercase' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {checklists.map(c => (
                <tr key={c.version} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  <td style={{ padding: '8px 0' }}><code style={{ fontSize: 12 }}>{c.version}</code></td>
                  <td style={{ padding: '8px 0' }}>{c.display_name}</td>
                  <td style={{ padding: '8px 0', color: 'var(--text-muted)' }}>{c.item_count}</td>
                  <td style={{ padding: '8px 0' }}>
                    {c.active ? <CheckCircle size={14} color="var(--green)" /> : <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Cases Manager
// ---------------------------------------------------------------------------
function CasesManager() {
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newTitle, setNewTitle] = useState('');

  const load = useCallback(() => {
    api.getChecklists ? null : null; // use api
    fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/v1/cases`, {
      headers: { Authorization: `Bearer ${getToken()}` }
    }).then(r => r.json()).then(data => { setCases(Array.isArray(data) ? data : []); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const createCase = async () => {
    if (!newTitle.trim()) return;
    try {
      await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/v1/cases`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getToken()}` },
        body: JSON.stringify({ title: newTitle.trim(), conversation_ids: [] }),
      });
      setNewTitle('');
      setCreating(false);
      load();
    } catch {}
  };

  const STATUS_MAP = { open: 'badge-amber', closed: 'badge-green', escalated: 'badge-red' };

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">Support Cases</span>
        <button className="btn btn-primary btn-sm" onClick={() => setCreating(c => !c)} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <Plus size={12} /> New Case
        </button>
      </div>
      {creating && (
        <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
          <input value={newTitle} onChange={e => setNewTitle(e.target.value)} placeholder="Case title…"
            onKeyDown={e => e.key === 'Enter' && createCase()}
            style={{ flex: 1, background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: 4, padding: '6px 10px', color: 'var(--text-primary)', fontSize: 13 }} />
          <button className="btn btn-primary btn-sm" onClick={createCase}>Create</button>
          <button className="btn btn-ghost btn-sm" onClick={() => setCreating(false)}>Cancel</button>
        </div>
      )}
      {loading ? <div className="skeleton" style={{ height: 40 }} /> : (
        cases.length === 0 ? <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>No cases yet.</p> : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr>
                {['Case ID', 'Title', 'Status', 'Conversations'].map(h => (
                  <th key={h} style={{ padding: '8px 0', textAlign: 'left', color: 'var(--text-muted)', fontSize: 11, fontWeight: 600, textTransform: 'uppercase' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {cases.map(c => (
                <tr key={c.case_id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  <td style={{ padding: '8px 0' }}><code style={{ fontSize: 11 }}>{c.case_id.slice(0, 8)}</code></td>
                  <td style={{ padding: '8px 0', fontWeight: 500 }}>{c.title}</td>
                  <td style={{ padding: '8px 0' }}><span className={`badge ${STATUS_MAP[c.status] || 'badge-gray'}`}>{c.status}</span></td>
                  <td style={{ padding: '8px 0', color: 'var(--text-muted)' }}>{c.conversation_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main AdminPanel
// ---------------------------------------------------------------------------
export default function AdminPanel() {
  const role = getUserRole();
  const [tab, setTab] = useState('budget');

  const tabs = [
    ['budget', 'Budget & Metrics'],
    ['audit', 'Audit Log'],
    ['checklists', 'Checklists'],
    ['cases', 'Cases'],
  ];

  if (!role || !['admin', 'supervisor'].includes(role)) {
    return <div className="page"><div className="error-banner">Admin or Supervisor role required.</div></div>;
  }

  return (
    <div className="page">
      <div style={{ marginBottom: 20 }}>
        <h1 style={{ fontSize: 22, fontWeight: 800, margin: 0 }}>Admin Panel</h1>
        <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '4px 0 0' }}>System monitoring, audit trail, policy management.</p>
      </div>
      <div style={{ display: 'flex', gap: 4, marginBottom: 20, borderBottom: '1px solid var(--border-subtle)' }}>
        {tabs.map(([id, label]) => (
          <button key={id} onClick={() => setTab(id)}
            style={{
              padding: '7px 14px', fontSize: 13, fontWeight: tab === id ? 700 : 400,
              color: tab === id ? 'var(--accent)' : 'var(--text-muted)',
              background: 'none', border: 'none',
              borderBottom: tab === id ? '2px solid var(--accent)' : '2px solid transparent',
              cursor: 'pointer', marginBottom: -1,
            }}>
            {label}
          </button>
        ))}
      </div>
      {tab === 'budget' && <BudgetCard />}
      {tab === 'audit' && <AuditLogTable />}
      {tab === 'checklists' && <ChecklistManager />}
      {tab === 'cases' && <CasesManager />}
    </div>
  );
}
