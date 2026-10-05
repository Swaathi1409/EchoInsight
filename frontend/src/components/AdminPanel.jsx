/**
 * AdminPanel: admin-only pages for audit logs, checklists, budget status, and cases.
 * Accessible from the sidebar when user role is admin or supervisor.
 */
import { useEffect, useState, useCallback, Fragment } from 'react';
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
// D21: Platform Metrics Card (replaces thin Budget-only view)
// ---------------------------------------------------------------------------
function MetricsStat({ label, value, sub, color }) {
  return (
    <div style={{ background: 'var(--bg-secondary)', borderRadius: 8, padding: '12px 16px', flex: 1, minWidth: 120 }}>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 26, fontWeight: 800, color: color || 'var(--text-primary)', lineHeight: 1.1 }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function BudgetCard() {
  const [budget, setBudget] = useState(null);
  const [convStats, setConvStats] = useState(null);
  const [err, setErr] = useState('');

  useEffect(() => {
    api.getBudgetStatus().then(setBudget).catch(e => setErr(e.message));
    // D21: Fetch conversation stats for platform metrics
    api.getConversations({ limit: 500 }).then(data => {
      const convs = Array.isArray(data) ? data : (data.items || []);
      const total = convs.length;
      const analyzed = convs.filter(c => c.analysis_version > 0).length;
      const pending = total - analyzed;
      const qaScores = convs.filter(c => c.qa_score != null).map(c => c.qa_score);
      const avgQA = qaScores.length ? (qaScores.reduce((a, b) => a + b, 0) / qaScores.length).toFixed(1) : null;
      const churnHigh = convs.filter(c => c.churn_risk === 'high').length;
      const churnMed = convs.filter(c => c.churn_risk === 'medium').length;
      const resolved = convs.filter(c => c.resolution === 'resolved').length;
      const unresolved = convs.filter(c => c.resolution === 'unresolved').length;
      const falseRes = convs.filter(c => c.false_resolution === true).length;
      setConvStats({ total, analyzed, pending, avgQA, churnHigh, churnMed, resolved, unresolved, falseRes });
    }).catch(() => {});
  }, []);

  if (err) return <div className="card"><div className="error-banner">{err}</div></div>;

  const pct = budget?.pct_used ?? 0;
  const color = pct >= 90 ? 'var(--red)' : pct >= 70 ? 'var(--amber)' : 'var(--green)';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Token Budget */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">Daily LLM Token Budget</span>
          {budget && <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{budget.date}</span>}
        </div>
        {!budget ? <div className="skeleton" style={{ height: 50 }} /> : (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 10 }}>
              <div style={{ fontSize: 28, fontWeight: 800, color }}>{budget.pct_used.toFixed(1)}%</div>
              <div>
                <div style={{ fontSize: 13 }}>{budget.used.toLocaleString()} / {budget.limit.toLocaleString()} tokens</div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{budget.remaining.toLocaleString()} remaining today</div>
              </div>
            </div>
            <div style={{ height: 8, background: 'var(--bg-secondary)', borderRadius: 4, overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${Math.min(pct, 100)}%`, background: color, borderRadius: 4, transition: 'width 0.4s ease' }} />
            </div>
          </>
        )}
      </div>

      {/* Platform Metrics */}
      <div className="card">
        <div className="card-header"><span className="card-title">Platform Metrics</span></div>
        {!convStats ? <div className="skeleton" style={{ height: 80 }} /> : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <MetricsStat label="Total Conversations" value={convStats.total} />
              <MetricsStat label="Analysed" value={convStats.analyzed} sub={`${convStats.pending} pending`} color="var(--green)" />
              <MetricsStat label="Avg QA Score" value={convStats.avgQA != null ? `${convStats.avgQA}` : '—'} sub="out of 100" />
              <MetricsStat label="False Resolutions" value={convStats.falseRes} color={convStats.falseRes > 0 ? 'var(--red)' : 'var(--green)'} />
            </div>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <MetricsStat label="Resolved" value={convStats.resolved} color="var(--green)" />
              <MetricsStat label="Unresolved" value={convStats.unresolved} color="var(--red)" />
              <MetricsStat label="High Churn Risk" value={convStats.churnHigh} color={convStats.churnHigh > 0 ? 'var(--red)' : 'var(--green)'} />
              <MetricsStat label="Medium Churn Risk" value={convStats.churnMed} color={convStats.churnMed > 0 ? 'var(--amber)' : 'var(--text-muted)'} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}


// ---------------------------------------------------------------------------
// D18: Human-readable action label map
// ---------------------------------------------------------------------------
const ACTION_LABELS = {
  create_conversation: 'Conversation created',
  end_conversation: 'Conversation ended',
  reopen_conversation: 'Conversation reopened',
  close_conversation: 'Conversation closed',
  append_turn: 'Turn appended',
  create_review: 'Review submitted',
  annotate_qa_item: 'QA item annotated',
  create_case: 'Case created',
  link_case: 'Case linked',
  checklist_activated: 'Checklist activated',
  submit_transcript: 'Transcript submitted',
};

function formatAuditDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
    + ', ' + d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  return (
    <button onClick={() => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
      style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 10, color: copied ? 'var(--green)' : 'var(--text-muted)', padding: '0 3px' }}
      title="Copy full ID">{copied ? 'Copied' : 'Copy'}</button>
  );
}

function AuditDetailModal({ log, onClose }) {
  if (!log) return null;
  // Filter null/undefined values from details to reduce noise
  const details = log.details || {};
  const filteredDetails = Object.fromEntries(
    Object.entries(details).filter(([, v]) => v !== null && v !== undefined)
  );
  const nullKeys = Object.keys(details).filter(k => details[k] === null || details[k] === undefined);
  return (
    <div style={{
      position: 'fixed', inset: 0,
      background: 'rgba(15, 23, 42, 0.85)',
      backdropFilter: 'blur(4px)',
      WebkitBackdropFilter: 'blur(4px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 1000,
      padding: 20
    }} onClick={onClose}>
      <div style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border-accent)',
        borderRadius: 'var(--radius)',
        padding: '24px 28px',
        width: '100%',
        maxWidth: 540,
        position: 'relative',
        animation: 'slideFadeIn 0.18s ease',
        boxShadow: '0 10px 30px rgba(0,0,0,0.3)',
      }} onClick={e => e.stopPropagation()}>
        <button onClick={onClose} title="Close"
          style={{ position: 'absolute', top: 14, right: 16, background: 'none', border: 'none',
            cursor: 'pointer', fontSize: 20, color: 'var(--text-muted)', lineHeight: 1 }}>×</button>

        <h3 style={{ margin: '0 0 20px 0', fontSize: 16, fontWeight: 700 }}>Audit Entry Details</h3>

        <div className="grid-2" style={{ gap: '16px 24px' }}>
          {/* Left column */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 3 }}>Action</div>
              <span className="badge badge-blue">{ACTION_LABELS[log.action] || log.action.replace(/_/g, ' ')}</span>
            </div>
            <div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 3 }}>Time</div>
              <div style={{ fontSize: 13 }}>{formatAuditDate(log.created_at)}</div>
            </div>
            <div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 3 }}>User</div>
              <div style={{ fontSize: 13 }}>{log.user_id != null ? `#${log.user_id}` : '—'}</div>
            </div>
            <div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 3 }}>Resource</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 2 }}>{log.resource_type}</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                {log.resource_id && log.resource_type === 'conversation' ? (
                  <a href={`#/conversation/${log.resource_id}`} style={{ color: 'var(--accent)', textDecoration: 'none' }} title="View Conversation">
                    <code style={{ fontSize: 11, wordBreak: 'break-all', color: 'inherit' }}>{log.resource_id}</code>
                  </a>
                ) : (
                  <code style={{ fontSize: 11, wordBreak: 'break-all' }}>{log.resource_id || '—'}</code>
                )}
                {log.resource_id && <CopyButton text={log.resource_id} />}
              </div>
            </div>
          </div>

          {/* Right column: Details */}
          <div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>Details</div>
            {Object.keys(filteredDetails).length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {Object.entries(filteredDetails).map(([k, v]) => (
                  <div key={k} className="insight-row" style={{ paddingTop: 4, paddingBottom: 4 }}>
                    <span className="insight-label" style={{ width: 'auto', marginRight: 8, fontSize: 10 }}>{k.replace(/_/g, ' ')}</span>
                    <code style={{ fontSize: 11, textAlign: 'right', flex: 1 }}>{typeof v === 'object' ? JSON.stringify(v) : String(v)}</code>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic' }}>No additional details recorded.</div>
            )}
            {nullKeys.length > 0 && (
              <div style={{ marginTop: 16, fontSize: 10, color: 'var(--text-muted)', lineHeight: 1.4 }}>
                <span style={{ fontWeight: 600 }}>Unset fields:</span> {nullKeys.map(k => k.replace(/_/g, ' ')).join(', ')}
                <br/>(Expected for Live Demo creation)
              </div>
            )}
          </div>
        </div>
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
  const [selectedLog, setSelectedLog] = useState(null);

  useEffect(() => {
    const params = filter ? { action: filter } : {};
    api.getAuditLogs(params).then(data => { setLogs(Array.isArray(data) ? data : []); setLoading(false); });
  }, [filter]);

  const actions = [...new Set(logs.map(l => l.action))].sort();

  return (
    <div className="card" style={{ padding: 0 }}>
      <div style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 10, borderBottom: '1px solid var(--border-subtle)', flexWrap: 'wrap' }}>
        <span className="card-title">Audit Log</span>
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{logs.length} entries</span>
        <select value={filter} onChange={e => setFilter(e.target.value)}
          style={{ marginLeft: 'auto', fontSize: 12, background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: 4, padding: '4px 8px', color: 'var(--text-primary)' }}>
          <option value="">All actions</option>
          {actions.map(a => <option key={a} value={a}>{ACTION_LABELS[a] || a}</option>)}
        </select>
      </div>
      {loading ? <div style={{ padding: 20 }}><div className="skeleton" style={{ height: 40 }} /></div> : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                {['Time', 'Action', 'User', 'Resource', ''].map(h => (
                  <th key={h} style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-muted)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {logs.length === 0 ? (
                <tr><td colSpan={5} style={{ padding: 24, textAlign: 'center', color: 'var(--text-muted)' }}>No audit entries yet.</td></tr>
              ) : logs.map(l => (
                <tr key={l.id} onClick={() => setSelectedLog(l)}
                  style={{ borderBottom: '1px solid var(--border-subtle)', cursor: 'pointer' }}
                  onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-secondary)'}
                  onMouseLeave={e => e.currentTarget.style.background = ''}>
                  <td style={{ padding: '8px 12px', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                    {formatAuditDate(l.created_at)}
                  </td>
                  <td style={{ padding: '8px 12px' }}>
                    <span className="badge badge-blue" style={{ whiteSpace: 'nowrap' }}>
                      {ACTION_LABELS[l.action] || l.action.replace(/_/g, ' ')}
                    </span>
                  </td>
                  <td style={{ padding: '8px 12px', color: 'var(--text-secondary)' }}>
                    {l.user_id != null ? `#${l.user_id}` : '—'}
                  </td>
                  <td style={{ padding: '8px 12px', color: 'var(--text-secondary)' }}>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{l.resource_type} / </span>
                    {l.resource_id && l.resource_type === 'conversation' ? (
                      <a href={`#/conversation/${l.resource_id}`} onClick={e => e.stopPropagation()} style={{ color: 'var(--accent)', textDecoration: 'none' }} title="View Conversation">
                        <code style={{ fontSize: 11, color: 'inherit' }}>{l.resource_id.slice(0, 8)}…</code>
                      </a>
                    ) : (
                      <code style={{ fontSize: 11 }}>{l.resource_id ? l.resource_id.slice(0, 8) + '…' : '—'}</code>
                    )}
                    {l.resource_id && <CopyButton text={l.resource_id} />}
                  </td>
                  <td style={{ padding: '8px 12px', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--text-muted)', fontSize: 11, textAlign: 'right' }}>
                    <span style={{ fontStyle: 'italic' }}>Click to view details</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {selectedLog && <AuditDetailModal log={selectedLog} onClose={() => setSelectedLog(null)} />}
    </div>
  );
}


// ---------------------------------------------------------------------------
// Checklist Manager
// ---------------------------------------------------------------------------
function ChecklistManager() {
  const [checklists, setChecklists] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editingKey, setEditingKey] = useState(null);
  const [editData, setEditData] = useState(null);
  const [saving, setSaving] = useState(false);

  const loadList = useCallback(() => {
    setLoading(true);
    api.getChecklists().then(data => { setChecklists(data); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  useEffect(() => { loadList(); }, [loadList]);

  const openEditor = async (key) => {
    try {
      const data = await api.getChecklist(key);
      setEditData(data);
      setEditingKey(key);
    } catch (e) { alert('Failed to load checklist details.'); }
  };

  const saveChecklist = async () => {
    if (!editData) return;
    setSaving(true);
    try {
      await api.createChecklistVersion(editingKey, {
        name: editData.name,
        description: editData.description,
        settings: editData.settings,
        items: editData.items
      });
      setEditingKey(null);
      setEditData(null);
      loadList();
    } catch (e) { alert('Failed to save checklist: ' + e.message); }
    finally { setSaving(false); }
  };

  if (editingKey && editData) {
    return (
      <div className="card">
        <div className="card-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <button className="btn btn-ghost btn-sm" onClick={() => setEditingKey(null)}>&larr; Back</button>
            <span className="card-title">Editing: {editData.name}</span>
            <span className="badge badge-amber">v{editData.active_version}</span>
          </div>
          <button className="btn btn-primary btn-sm" onClick={saveChecklist} disabled={saving}>{saving ? 'Saving...' : 'Save as New Version'}</button>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, padding: 16 }}>
          <div style={{ display: 'flex', gap: 10 }}>
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: 11, color: 'var(--text-muted)' }}>Name</label>
              <input value={editData.name} onChange={e => setEditData({...editData, name: e.target.value})} className="input" style={{ width: '100%', boxSizing: 'border-box' }} />
            </div>
            <div style={{ flex: 2 }}>
              <label style={{ fontSize: 11, color: 'var(--text-muted)' }}>Description</label>
              <input value={editData.description || ''} onChange={e => setEditData({...editData, description: e.target.value})} className="input" style={{ width: '100%', boxSizing: 'border-box' }} />
            </div>
          </div>
          <h4 style={{ margin: '16px 0 8px', fontSize: 14 }}>Items</h4>
          {editData.items.map((item, i) => (
            <div key={i} style={{ border: '1px solid var(--border-subtle)', padding: 10, borderRadius: 6, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <div style={{ minWidth: 150, flex: 2 }}>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Key</div>
                <input value={item.item_key} disabled className="input" style={{ width: '100%', boxSizing: 'border-box', opacity: 0.6 }} />
              </div>
              <div style={{ minWidth: 200, flex: 3 }}>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Display Name</div>
                <input value={item.display_name} onChange={e => { const items = [...editData.items]; items[i].display_name = e.target.value; setEditData({...editData, items}); }} className="input" style={{ width: '100%', boxSizing: 'border-box' }} />
              </div>
              <div style={{ minWidth: 100, flex: 1 }}>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Weight</div>
                <input type="number" step="0.1" value={item.weight} onChange={e => { const items = [...editData.items]; items[i].weight = parseFloat(e.target.value); setEditData({...editData, items}); }} className="input" style={{ width: '100%', boxSizing: 'border-box' }} />
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, paddingTop: 16 }}>
                <label style={{ fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}><input type="checkbox" checked={item.enabled} onChange={e => { const items = [...editData.items]; items[i].enabled = e.target.checked; setEditData({...editData, items}); }} /> Enabled</label>
                <label style={{ fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}><input type="checkbox" checked={item.critical} onChange={e => { const items = [...editData.items]; items[i].critical = e.target.checked; setEditData({...editData, items}); }} /> Critical</label>
                <label style={{ fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}><input type="checkbox" checked={item.required} onChange={e => { const items = [...editData.items]; items[i].required = e.target.checked; setEditData({...editData, items}); }} /> Required</label>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">QA Checklists</span>
      </div>
      {loading ? <div className="skeleton" style={{ height: 40 }} /> : (
        checklists.length === 0 ? (
          <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>No checklists found.</p>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr>
                {['Version', 'Name', 'Active', 'Updated', 'Actions'].map(h => (
                  <th key={h} style={{ padding: '8px 0', textAlign: 'left', color: 'var(--text-muted)', fontSize: 11, fontWeight: 600, textTransform: 'uppercase' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {checklists.map(c => (
                <tr key={c.key} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  <td style={{ padding: '8px 0' }}><code style={{ fontSize: 12 }}>v{c.active_version}</code></td>
                  <td style={{ padding: '8px 0' }}>{c.name}</td>
                  <td style={{ padding: '8px 0' }}>{c.active_version_id ? <CheckCircle size={14} color="var(--green)" /> : <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>—</span>}</td>
                  <td style={{ padding: '8px 0', color: 'var(--text-muted)' }}>{c.updated_at ? new Date(c.updated_at).toLocaleString() : '—'}</td>
                  <td style={{ padding: '8px 0' }}><button className="btn btn-ghost btn-sm" onClick={() => openEditor(c.key)}>Edit</button></td>
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
  const [expanded, setExpanded] = useState({});
  const [linkInputs, setLinkInputs] = useState({});

  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  const load = useCallback(() => {
    fetch(`${API_URL}/api/v1/cases`, {
      headers: { Authorization: `Bearer ${getToken()}` }
    }).then(r => r.json()).then(data => { setCases(Array.isArray(data) ? data : []); setLoading(false); })
      .catch(() => setLoading(false));
  }, [API_URL]);

  useEffect(() => { load(); }, [load]);

  const createCase = async () => {
    if (!newTitle.trim()) return;
    try {
      await fetch(`${API_URL}/api/v1/cases`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getToken()}` },
        body: JSON.stringify({ title: newTitle.trim(), conversation_ids: [] }),
      });
      setNewTitle('');
      setCreating(false);
      load();
    } catch {}
  };

  const linkConv = async (caseId) => {
    const cid = linkInputs[caseId] || '';
    if (!cid.trim()) return;
    try {
      await fetch(`${API_URL}/api/v1/cases/${caseId}/conversations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getToken()}` },
        body: JSON.stringify({ conversation_id: cid.trim() })
      });
      setLinkInputs(p => ({ ...p, [caseId]: '' }));
      load();
    } catch (e) { alert('Error linking: ' + e.message); }
  };

  const unlinkConv = async (caseId, convId) => {
    if (!confirm('Unlink conversation?')) return;
    try {
      await fetch(`${API_URL}/api/v1/cases/${caseId}/conversations/${convId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${getToken()}` }
      });
      load();
    } catch (e) { alert('Error unlinking: ' + e.message); }
  };

  const STATUS_MAP = { open: 'badge-amber', closed: 'badge-green', escalated: 'badge-red' };

  const toggleExpand = (caseId) => setExpanded(e => ({ ...e, [caseId]: !e[caseId] }));

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
          <input value={newTitle} onChange={e => setNewTitle(e.target.value)} placeholder="Case title..."
            onKeyDown={e => e.key === 'Enter' && createCase()}
            style={{ flex: 1, background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: 4, padding: '6px 10px', color: 'var(--text-primary)', fontSize: 13 }} />
          <button className="btn btn-primary btn-sm" onClick={createCase}>Create</button>
          <button className="btn btn-ghost btn-sm" onClick={() => setCreating(false)}>Cancel</button>
        </div>
      )}
      {loading ? <div className="skeleton" style={{ height: 40 }} /> : (
        cases.length === 0 ? <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>No cases yet.</p> : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            {cases.map(c => (
              <div key={c.case_id} style={{ borderBottom: '1px solid var(--border-subtle)', padding: '10px 0' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }} onClick={() => toggleExpand(c.case_id)}>
                  <code style={{ fontSize: 11, color: 'var(--text-muted)' }}>{c.case_id.slice(0, 8)}</code>
                  <span style={{ flex: 1, fontWeight: 500, fontSize: 13 }}>{c.title}</span>
                  <span className={`badge ${STATUS_MAP[c.status] || 'badge-gray'}`}>{c.status}</span>
                  <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{c.conversation_count} conv{c.conversation_count !== 1 ? 's' : ''}</span>
                  {c.created_at && <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{new Date(c.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}</span>}
                  <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{expanded[c.case_id] ? '▲' : '▼'}</span>
                </div>
                {/* Expanded conversation links */}
                {expanded[c.case_id] && (
                  <div style={{ paddingTop: 8, paddingLeft: 16 }}>
                    {c.notes && <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>{c.notes}</p>}
                    
                    <div style={{ display: 'flex', gap: 6, marginBottom: 12, marginTop: 8 }}>
                      <input value={linkInputs[c.case_id] || ''} onChange={e => setLinkInputs({ ...linkInputs, [c.case_id]: e.target.value })}
                        placeholder="Paste Conversation ID to link..."
                        style={{ flex: 1, maxWidth: 300, background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: 4, padding: '4px 8px', fontSize: 12, color: 'var(--text-primary)' }}
                        onKeyDown={e => e.key === 'Enter' && linkConv(c.case_id)} />
                      <button className="btn btn-primary btn-sm" onClick={() => linkConv(c.case_id)} style={{ fontSize: 11, padding: '2px 8px' }}>Link</button>
                    </div>

                    {(c.conversations || []).length === 0 ? (
                      <p style={{ fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic', margin: 0 }}>No conversations linked.</p>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 2 }}>Linked Conversations</div>
                        {c.conversations.map(conv => (
                          <div key={conv.conversation_id} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <a href={`#/conversation/${conv.conversation_id}`}
                              style={{ fontSize: 12, color: 'var(--accent)', fontFamily: 'monospace', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 4 }}
                              title={conv.conversation_id}>
                              <Link size={11} /> {conv.conversation_id.slice(0, 8)}...
                            </a>
                            <button className="btn btn-ghost btn-sm" style={{ padding: '0 4px', height: 20, color: 'var(--red)', fontSize: 10 }} onClick={() => unlinkConv(c.case_id, conv.conversation_id)}>unlink</button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
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
        <h2 style={{ fontSize: 22, fontWeight: 800, margin: 0 }}>Admin Panel</h2>
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
