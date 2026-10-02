import { useEffect, useState, useCallback } from 'react';
import { api } from '../api';
import {
  AlertCircle, Clock, CheckCircle, XCircle, TrendingUp,
  RefreshCw, Filter, Search, ChevronDown, ChevronUp,
  Users, Shield, BarChart2, AlertTriangle, Activity,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Tiny chart helpers (no Recharts dependency required; pure CSS bars)
// ---------------------------------------------------------------------------

function BarChart({ data, colorKey }) {
  if (!data || data.length === 0) return <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>No data</div>;
  const max = Math.max(...data.map(d => d.value), 1);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {data.map(({ label, value, color }) => (
        <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ width: 140, fontSize: 11, color: 'var(--text-secondary)', textAlign: 'right', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {label.replace(/_/g, ' ')}
          </div>
          <div style={{ flex: 1, height: 14, background: 'var(--bg-secondary)', borderRadius: 3, overflow: 'hidden' }}>
            <div style={{ height: '100%', width: `${(value / max) * 100}%`, background: color || 'var(--accent)', borderRadius: 3, transition: 'width 0.4s ease' }} />
          </div>
          <div style={{ width: 28, fontSize: 11, color: 'var(--text-muted)', textAlign: 'right' }}>{value}</div>
        </div>
      ))}
    </div>
  );
}

function DonutSegments({ data }) {
  if (!data || data.length === 0) return <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>No data</div>;
  const total = data.reduce((s, d) => s + d.value, 0) || 1;
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
      {data.map(({ label, value, color }) => (
        <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{ width: 10, height: 10, borderRadius: 2, background: color || 'var(--accent)', flexShrink: 0 }} />
          <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
            {label.replace(/_/g, ' ')} — {value} ({((value / total) * 100).toFixed(0)}%)
          </span>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Resolution color map
// ---------------------------------------------------------------------------
const RESOLUTION_COLORS = {
  resolved: 'var(--green)',
  partially_resolved: 'var(--amber)',
  pending: '#6366f1',
  unresolved: 'var(--red)',
  escalated: '#ec4899',
  unknown: 'var(--text-muted)',
};
const STATUS_COLORS = {
  active: 'var(--amber)',
  ended: 'var(--green)',
  created: '#6366f1',
  closed: 'var(--text-muted)',
};

// ---------------------------------------------------------------------------
// KPI Card
// ---------------------------------------------------------------------------
function KPICard({ icon, label, value, sub, color }) {
  return (
    <div className="card" style={{ display: 'flex', alignItems: 'flex-start', gap: 14, padding: '18px 20px' }}>
      <div style={{ background: `${color}22`, borderRadius: 10, padding: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
        {icon}
      </div>
      <div>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>{label}</div>
        <div style={{ fontSize: 26, fontWeight: 800, color: 'var(--text-primary)', lineHeight: 1 }}>{value ?? '—'}</div>
        {sub && <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>{sub}</div>}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Score bar
// ---------------------------------------------------------------------------
function ScoreBar({ score, coverage }) {
  if (score == null) return <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>—</span>;
  const color = score >= 80 ? 'var(--green)' : score >= 60 ? 'var(--amber)' : 'var(--red)';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ width: 60, height: 6, background: 'var(--bg-secondary)', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${score}%`, background: color, borderRadius: 3 }} />
      </div>
      <span style={{ fontSize: 12, color, fontWeight: 600 }}>{score}</span>
      {coverage != null && coverage < 0.7 && (
        <span style={{ fontSize: 10, color: 'var(--amber)', background: 'var(--amber-bg)', padding: '1px 5px', borderRadius: 3 }}>partial</span>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Risk badge
// ---------------------------------------------------------------------------
function RiskBadge({ risk }) {
  const map = { low: 'badge-green', medium: 'badge-amber', high: 'badge-red' };
  if (!risk) return null;
  return <span className={`badge ${map[risk] || 'badge-gray'}`}>{risk}</span>;
}

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------
function StatusBadge({ status }) {
  const map = { ended: 'badge-green', active: 'badge-amber', created: 'badge-blue' };
  return <span className={`badge ${map[status] || 'badge-gray'}`}>{status}</span>;
}

// ---------------------------------------------------------------------------
// Main Dashboard
// ---------------------------------------------------------------------------
export default function Dashboard({ onSelectConv }) {
  const [convs, setConvs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');

  // Filters
  const [statusFilter, setStatusFilter] = useState('');
  const [search, setSearch] = useState('');
  const initTab = () => {
    try { return window.location.hash.split('?tab=')[1] || 'overview'; }
    catch { return 'overview'; }
  };
  const [activeTab, setActiveTab] = useState(initTab()); // overview | conversations | commitments | false_resolutions

  // Secondary data
  const [commitments, setCommitments] = useState([]);
  const [falseResolutions, setFalseResolutions] = useState([]);

  // Sorting
  const [sortKey, setSortKey] = useState('started_at');
  const [sortDir, setSortDir] = useState('desc');

  const loadAll = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    else setRefreshing(true);
    try {
      const params = { limit: 200 };
      if (statusFilter) params.status = statusFilter;
      // Primary: conversations list — must succeed
      const data = await api.getConversations(params);
      setConvs(Array.isArray(data) ? data : []);
      setError('');
      // Secondary: non-fatal — silently ignore failures
      const [ocResult, frResult] = await Promise.allSettled([
        api.getOpenCommitments(50),
        api.getFalseResolutions(),
      ]);
      
      if (ocResult.status === 'fulfilled') {
        const flatCommitments = [];
        const raw = Array.isArray(ocResult.value) ? ocResult.value : [];
        raw.forEach(c => {
          (c.open_commitments || []).forEach(com => {
            flatCommitments.push({ conversation_id: c.conversation_id || c.id, ...com });
          });
        });
        setCommitments(flatCommitments);
      }
      
      if (frResult.status === 'fulfilled') setFalseResolutions(Array.isArray(frResult.value) ? frResult.value : []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [statusFilter]);

  useEffect(() => { loadAll(); }, [loadAll]);

  // Auto-refresh every 30s
  useEffect(() => {
    const t = setInterval(() => loadAll(true), 30000);
    return () => clearInterval(t);
  }, [loadAll]);

  // ---------------------------------------------------------------------------
  // Derived stats for KPIs and charts
  // ---------------------------------------------------------------------------
  const total = convs.length;
  const ended = convs.filter(c => c.status === 'ended').length;
  const active = convs.filter(c => c.status === 'active').length;

  const withQA = convs.filter(c => c.qa_score != null);
  const avgQA = withQA.length
    ? Math.round(withQA.reduce((s, c) => s + c.qa_score, 0) / withQA.length)
    : null;

  const resolved = convs.filter(c => {
    const r = c.resolution || (c.analysis?.resolution);
    return r === 'resolved';
  }).length;

  const withFR = convs.filter(c => c.false_resolution).length;
  const openCommitCount = commitments.length;

  // Resolution distribution
  const resolutionCounts = {};
  convs.forEach(c => {
    const r = c.analysis?.resolution || 'unknown';
    resolutionCounts[r] = (resolutionCounts[r] || 0) + 1;
  });
  const resolutionData = Object.entries(resolutionCounts)
    .map(([label, value]) => ({ label, value, color: RESOLUTION_COLORS[label] }))
    .sort((a, b) => b.value - a.value);

  // Call reason distribution (from analysis)
  const reasonCounts = {};
  convs.forEach(c => {
    (c.analysis?.reasons || []).forEach(r => {
      reasonCounts[r] = (reasonCounts[r] || 0) + 1;
    });
  });
  const reasonData = Object.entries(reasonCounts)
    .map(([label, value]) => ({ label, value, color: 'var(--accent)' }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 10);

  // Churn risk distribution
  const churnCounts = { low: 0, medium: 0, high: 0 };
  convs.forEach(c => {
    const r = c.churn_risk || 'low';
    churnCounts[r] = (churnCounts[r] || 0) + 1;
  });
  const churnData = [
    { label: 'Low', value: churnCounts.low, color: 'var(--green)' },
    { label: 'Medium', value: churnCounts.medium, color: 'var(--amber)' },
    { label: 'High', value: churnCounts.high, color: 'var(--red)' },
  ].filter(d => d.value > 0);

  // ---------------------------------------------------------------------------
  // Filtered + sorted conversation list
  // ---------------------------------------------------------------------------
  const filtered = convs.filter(c => {
    if (search) {
      const q = search.toLowerCase();
      return c.id?.includes(q) || c.agent_id?.includes(q) || c.source_id?.toLowerCase().includes(q);
    }
    return true;
  }).sort((a, b) => {
    let av = a[sortKey] ?? '';
    let bv = b[sortKey] ?? '';
    if (typeof av === 'string') av = av.toLowerCase();
    if (typeof bv === 'string') bv = bv.toLowerCase();
    return sortDir === 'asc' ? (av > bv ? 1 : -1) : (av < bv ? 1 : -1);
  });

  const toggleSort = (key) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('desc'); }
  };

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  if (loading) return (
    <div className="page">
      {[1, 2, 3, 4].map(i => <div key={i} className="skeleton" style={{ height: 90, marginBottom: 12 }} />)}
    </div>
  );

  return (
    <div className="page">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 800, margin: 0 }}>Conversation Intelligence</h1>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '4px 0 0' }}>
            {total} conversations — last refreshed {new Date().toLocaleTimeString()}
          </p>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={() => loadAll(true)} disabled={refreshing}
          style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <RefreshCw size={13} style={{ animation: refreshing ? 'spin 1s linear infinite' : 'none' }} />
          {refreshing ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      {error && <div className="error-banner" style={{ marginBottom: 16 }}>{error}</div>}

      {/* KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12, marginBottom: 24 }}>
        <KPICard icon={<Activity size={20} color="var(--accent)" />} label="Total Analyzed" value={total}
          sub={`${active} active`} color="var(--accent)" />
        <KPICard icon={<CheckCircle size={20} color="var(--green)" />} label="Resolved" value={resolved}
          sub={total ? `${((resolved / total) * 100).toFixed(0)}% of all` : ''} color="var(--green)" />
        <KPICard icon={<BarChart2 size={20} color="var(--accent)" />} label="Avg QA Score" value={avgQA}
          sub={`${withQA.length} scored`} color="var(--accent)" />
        <KPICard icon={<AlertCircle size={20} color="var(--amber)" />} label="Open Commitments" value={openCommitCount}
          color="var(--amber)" />
        <KPICard icon={<AlertTriangle size={20} color="var(--red)" />} label="False Resolutions" value={withFR}
          color="var(--red)" />
        <KPICard icon={<Shield size={20} color="var(--red)" />} label="High Churn Risk" value={churnCounts.high}
          color="var(--red)" />
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 20, borderBottom: '1px solid var(--border-subtle)', paddingBottom: 0 }}>
        {[
          ['overview', 'Overview'],
          ['conversations', 'Conversations'],
          ['commitments', `Open Commitments (${openCommitCount})`],
          ['false_resolutions', `False Resolutions (${withFR})`],
        ].map(([id, label]) => (
          <button key={id} onClick={() => setActiveTab(id)}
            style={{
              padding: '8px 16px', fontSize: 13, fontWeight: activeTab === id ? 700 : 400,
              color: activeTab === id ? 'var(--accent)' : 'var(--text-muted)',
              background: 'none', border: 'none', borderBottom: activeTab === id ? '2px solid var(--accent)' : '2px solid transparent',
              cursor: 'pointer', marginBottom: -1,
            }}>
            {label}
          </button>
        ))}
      </div>

      {/* ---- OVERVIEW TAB ---- */}
      {activeTab === 'overview' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div className="card">
            <div className="card-header"><span className="card-title">Resolution Distribution</span></div>
            <DonutSegments data={resolutionData} />
            <div style={{ marginTop: 16 }}><BarChart data={resolutionData} /></div>
          </div>
          <div className="card">
            <div className="card-header"><span className="card-title">Churn Risk Distribution</span></div>
            <DonutSegments data={churnData} />
            <div style={{ marginTop: 16 }}><BarChart data={churnData} /></div>
          </div>
          <div className="card" style={{ gridColumn: '1 / -1' }}>
            <div className="card-header"><span className="card-title">Top Call Reasons</span></div>
            {reasonData.length > 0
              ? <BarChart data={reasonData} />
              : <p style={{ color: 'var(--text-muted)', fontSize: 12 }}>No analysis data yet — conversations must be ended and analyzed first.</p>
            }
          </div>
        </div>
      )}

      {/* ---- CONVERSATIONS TAB ---- */}
      {activeTab === 'conversations' && (
        <>
          {/* Filters */}
          <div style={{ display: 'flex', gap: 10, marginBottom: 14, flexWrap: 'wrap', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'var(--bg-secondary)', borderRadius: 6, padding: '6px 10px', border: '1px solid var(--border-subtle)' }}>
              <Search size={13} color="var(--text-muted)" />
              <input
                placeholder="Search ID or agent…" value={search}
                onChange={e => setSearch(e.target.value)}
                style={{ background: 'none', border: 'none', outline: 'none', fontSize: 13, color: 'var(--text-primary)', width: 180 }}
              />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Filter size={13} color="var(--text-muted)" />
              <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
                style={{ fontSize: 13, background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '6px 8px', color: 'var(--text-primary)', cursor: 'pointer' }}>
                <option value="">All statuses</option>
                <option value="active">Active</option>
                <option value="ended">Ended</option>
                <option value="created">Created</option>
              </select>
            </div>
            <span style={{ fontSize: 12, color: 'var(--text-muted)', marginLeft: 'auto' }}>{filtered.length} rows</span>
          </div>

          {/* Table */}
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                    {[
                      ['id', 'ID'],
                      ['status', 'Status'],
                      ['started_at', 'Started'],
                      ['turn_count', 'Turns'],
                      ['qa_score', 'QA Score'],
                      ['churn_risk', 'Churn'],
                    ].map(([key, label]) => (
                      <th key={key} onClick={() => toggleSort(key)} style={{ padding: '10px 12px', textAlign: 'left', cursor: 'pointer', color: 'var(--text-muted)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.05em', whiteSpace: 'nowrap', userSelect: 'none' }}>
                        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                          {label}
                          {sortKey === key && (sortDir === 'asc' ? <ChevronUp size={11} /> : <ChevronDown size={11} />)}
                        </span>
                      </th>
                    ))}
                    <th style={{ padding: '10px 12px', textAlign: 'left', color: 'var(--text-muted)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase' }}>False Res.</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.length === 0 ? (
                    <tr><td colSpan={7} style={{ padding: 32, textAlign: 'center', color: 'var(--text-muted)' }}>No conversations found.</td></tr>
                  ) : filtered.map(c => (
                    <tr key={c.id} onClick={() => onSelectConv && onSelectConv(c.id)}
                      style={{ borderBottom: '1px solid var(--border-subtle)', cursor: 'pointer', transition: 'background 0.15s' }}
                      onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-secondary)'}
                      onMouseLeave={e => e.currentTarget.style.background = ''}>
                      <td style={{ padding: '10px 12px' }}>
                        <code style={{ fontSize: 12, background: 'var(--bg-secondary)', padding: '2px 5px', borderRadius: 4 }}>{c.id.slice(0, 8)}</code>
                        {c.synthetic_assignment && <span className="synthetic-label" style={{ marginLeft: 5 }}>synthetic</span>}
                      </td>
                      <td style={{ padding: '10px 12px' }}><StatusBadge status={c.status} /></td>
                      <td style={{ padding: '10px 12px', color: 'var(--text-muted)', fontSize: 12 }}>{c.started_at ? new Date(c.started_at).toLocaleString() : '—'}</td>
                      <td style={{ padding: '10px 12px', textAlign: 'center' }}>{c.turn_count ?? '—'}</td>
                      <td style={{ padding: '10px 12px' }}><ScoreBar score={c.qa_score} /></td>
                      <td style={{ padding: '10px 12px' }}><RiskBadge risk={c.churn_risk} /></td>
                      <td style={{ padding: '10px 12px' }}>
                        {c.false_resolution ? <span className="badge badge-red">Detected</span> : <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>—</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* ---- OPEN COMMITMENTS TAB ---- */}
      {activeTab === 'commitments' && (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          {commitments.length === 0 ? (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>No open commitments.</div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  {['Conversation', 'Description', 'Owner', 'Deadline', 'Status'].map(h => (
                    <th key={h} style={{ padding: '10px 12px', textAlign: 'left', color: 'var(--text-muted)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {commitments.map((c, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid var(--border-subtle)' }}
                    onClick={() => onSelectConv && onSelectConv(c.conversation_id)}
                    onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-secondary)'}
                    onMouseLeave={e => e.currentTarget.style.background = ''}
                    style={{ cursor: 'pointer' }}>
                    <td style={{ padding: '10px 12px' }}><code style={{ fontSize: 12 }}>{c.conversation_id?.slice(0, 8)}</code></td>
                    <td style={{ padding: '10px 12px', maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.description}</td>
                    <td style={{ padding: '10px 12px', color: 'var(--text-muted)' }}>{c.owner || '—'}</td>
                    <td style={{ padding: '10px 12px', color: 'var(--text-muted)' }}>
                      {c.deadline || '—'}
                      {c.deadline_flag && <span className="badge badge-amber" style={{ marginLeft: 5 }}>{c.deadline_flag}</span>}
                    </td>
                    <td style={{ padding: '10px 12px' }}><span className="badge badge-amber">{c.status}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* ---- FALSE RESOLUTIONS TAB ---- */}
      {activeTab === 'false_resolutions' && (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          {falseResolutions.length === 0 ? (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>No false resolutions detected.</div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  {['Conversation', 'Detected At', 'QA Score', 'Reason'].map(h => (
                    <th key={h} style={{ padding: '10px 12px', textAlign: 'left', color: 'var(--text-muted)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {falseResolutions.map(c => {
                  const convId = c.conversation_id || c.id;
                  const matchingConv = convs.find(x => x.id === convId);
                  return (
                    <tr key={convId} style={{ borderBottom: '1px solid var(--border-subtle)', cursor: 'pointer' }}
                      onClick={() => onSelectConv && onSelectConv(convId)}
                      onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-secondary)'}
                      onMouseLeave={e => e.currentTarget.style.background = ''}>
                      <td style={{ padding: '10px 12px' }}><code style={{ fontSize: 12 }}>{convId?.slice(0, 8)}</code></td>
                      <td style={{ padding: '10px 12px', color: 'var(--text-muted)', fontSize: 12 }}>{c.created_at ? new Date(c.created_at).toLocaleString() : '—'}</td>
                      <td style={{ padding: '10px 12px' }}><ScoreBar score={matchingConv?.qa_score} /></td>
                      <td style={{ padding: '10px 12px', maxWidth: 300, color: 'var(--text-secondary)', fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {c.false_resolution_reason || c.analysis?.false_resolution_reason || '—'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
