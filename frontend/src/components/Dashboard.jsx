import { useEffect, useState, useCallback } from 'react';
import { api } from '../api';
import {
  AlertCircle, Clock, CheckCircle, XCircle, TrendingUp,
  RefreshCw, Filter, Search, ChevronDown, ChevronUp,
  Users, Shield, BarChart2, AlertTriangle, Activity, Zap,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Premium bar chart — animated fills, left-side labels
// ---------------------------------------------------------------------------
function BarChart({ data }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => { const t = setTimeout(() => setMounted(true), 60); return () => clearTimeout(t); }, []);
  if (!data || data.length === 0) return <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: '8px 0' }}>No data</div>;
  const max = Math.max(...data.map(d => d.value), 1);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
      {data.map(({ label, value, color }) => {
        const pct = (value / max) * 100;
        return (
          <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 150, fontSize: 11, color: 'var(--text-secondary)', textAlign: 'right', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', flexShrink: 0 }}
              title={label.replace(/_/g, ' ')}>
              {label.replace(/_/g, ' ')}
            </div>
            <div style={{ flex: 1, height: 16, background: 'var(--bg-secondary)', borderRadius: 4, overflow: 'hidden', position: 'relative' }}>
              <div style={{
                height: '100%',
                width: mounted ? `${pct}%` : '0%',
                background: color || 'var(--accent)',
                borderRadius: 4,
                transition: 'width 0.55s cubic-bezier(0.4,0,0.2,1)',
                opacity: 0.85,
              }} />
            </div>
            <div style={{ width: 28, fontSize: 12, color: 'var(--text-muted)', textAlign: 'right', fontWeight: 600, flexShrink: 0 }}>{value}</div>
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// SVG donut chart
// ---------------------------------------------------------------------------
function DonutChart({ data, size = 100 }) {
  if (!data || data.length === 0) return <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>No data</div>;
  const total = data.reduce((s, d) => s + d.value, 0) || 1;
  const cx = size / 2, cy = size / 2, r = size * 0.38, stroke = size * 0.13;
  const circumference = 2 * Math.PI * r;
  let offset = 0;
  const segments = data.map(({ label, value, color }) => {
    const dash = (value / total) * circumference;
    const seg = { label, value, color, dash, gap: circumference - dash, offset };
    offset += dash;
    return seg;
  });
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)', flexShrink: 0 }}>
        {segments.map((s, i) => (
          <circle key={i} cx={cx} cy={cy} r={r}
            fill="none"
            stroke={s.color || 'var(--accent)'}
            strokeWidth={stroke}
            strokeDasharray={`${s.dash} ${s.gap}`}
            strokeDashoffset={-s.offset}
            strokeLinecap="butt"
            opacity={0.85}
          />
        ))}
      </svg>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {data.map(({ label, value, color }) => (
          <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 10, height: 10, borderRadius: 2, background: color || 'var(--accent)', flexShrink: 0 }} />
            <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
              {label.replace(/_/g, ' ')}
              <span style={{ marginLeft: 5, fontWeight: 700, color: 'var(--text-primary)' }}>{value}</span>
              <span style={{ marginLeft: 4, color: 'var(--text-muted)', fontSize: 11 }}>({((value / (data.reduce((s,d)=>s+d.value,0)||1)) * 100).toFixed(0)}%)</span>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Resolution / status colors
// ---------------------------------------------------------------------------
const RESOLUTION_COLORS = {
  resolved:           'var(--green)',
  partially_resolved: 'var(--amber)',
  pending:            '#6366f1',
  unresolved:         'var(--red)',
  escalated:          '#ec4899',
  unknown:            'var(--text-muted)',
};
const STATUS_COLORS = {
  active: 'var(--amber)', ended: 'var(--green)', created: '#6366f1', closed: 'var(--text-muted)',
};

// ---------------------------------------------------------------------------
// KPI Card — premium with animated accent line
// ---------------------------------------------------------------------------
function KPICard({ icon, label, value, sub, color, accentColor }) {
  const accent = accentColor || color || 'var(--accent)';
  return (
    <div className="card" style={{
      display: 'flex', flexDirection: 'column', gap: 12, padding: '16px',
      position: 'relative', overflow: 'hidden',
      '--kpi-color': accent,
      height: '100%', boxSizing: 'border-box'
    }}>
      <div style={{
        background: `${accent}18`, borderRadius: 8, padding: 8,
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center', alignSelf: 'flex-start'
      }}>
        {icon}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6 }}>{label}</div>
        <div style={{ fontSize: 28, fontWeight: 800, color: 'var(--text-heading)', lineHeight: 1 }}>{value ?? '—'}</div>
        {sub && <div style={{ marginTop: 'auto', paddingTop: 8, fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.3 }}>{sub}</div>}
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
      <div style={{ width: 60, height: 5, background: 'var(--bg-secondary)', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${score}%`, background: color, borderRadius: 3 }} />
      </div>
      <span style={{ fontSize: 12, color, fontWeight: 700 }}>{score}</span>
      {coverage != null && coverage < 0.7 && (
        <span style={{ fontSize: 10, color: 'var(--amber)', background: 'var(--amber-soft)', padding: '1px 5px', borderRadius: 3 }}>partial</span>
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
  // D3: analyzed means a final analysis exists (analysis_version > 0)
  const analyzed = convs.filter(c => (c.analysis_version || 0) > 0).length;
  const pendingAnalysis = ended - convs.filter(c => c.status === 'ended' && (c.analysis_version || 0) > 0).length;

  const withQA = convs.filter(c => c.qa_score != null);
  const avgQA = withQA.length
    ? Math.round(withQA.reduce((s, c) => s + c.qa_score, 0) / withQA.length)
    : null;

  const resolved = convs.filter(c => c.resolution === 'resolved').length;

  const withFR = convs.filter(c => c.false_resolution).length;
  const openCommitCount = commitments.length;

  // Resolution distribution - use top-level resolution field from list API
  const resolutionCounts = {};
  convs.forEach(c => {
    const r = c.resolution || (c.status === 'active' ? 'active' : 'unknown');
    resolutionCounts[r] = (resolutionCounts[r] || 0) + 1;
  });
  const resolutionData = Object.entries(resolutionCounts)
    .map(([label, value]) => ({ label, value, color: RESOLUTION_COLORS[label] }))
    .sort((a, b) => b.value - a.value);

  // Call reason distribution - use top-level reasons field from list API
  const reasonCounts = {};
  convs.forEach(c => {
    (c.reasons || []).forEach(r => {
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
          <h2 style={{ fontSize: 22, fontWeight: 800, margin: 0 }}>EchoInsight Overview</h2>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '4px 0 0' }}>
            {total} conversations — {active} active — last refreshed {new Date().toLocaleTimeString()}
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
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 12, marginBottom: 24 }}>
        <KPICard icon={<Activity size={20} color="var(--accent)" />} label="Total Analyzed" value={analyzed}
          sub={`${active} active${pendingAnalysis > 0 ? ` · ${pendingAnalysis} pending analysis` : ''}`} color="var(--accent)" />
        <KPICard icon={<CheckCircle size={20} color="var(--green)" />} label="Resolved" value={resolved}
          sub={analyzed ? `${((resolved / analyzed) * 100).toFixed(0)}% of analyzed` : ''} color="var(--green)" />
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
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Health Summary Bar */}
          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12,
            padding: '16px 20px', background: 'var(--bg-card)', borderRadius: 'var(--radius)',
            border: '1px solid var(--border)',
          }}>
            {[
              { label: 'Resolution Rate', value: analyzed > 0 ? `${((resolved / analyzed) * 100).toFixed(0)}%` : '—', sub: `${resolved} of ${analyzed} analyzed`, color: 'var(--green)' },
              { label: 'False Resolution Rate', value: analyzed > 0 ? `${((withFR / analyzed) * 100).toFixed(0)}%` : '—', sub: `${withFR} flagged`, color: withFR > 0 ? 'var(--red)' : 'var(--green)' },
              { label: 'High Churn Exposure', value: total > 0 ? `${((churnCounts.high / total) * 100).toFixed(0)}%` : '—', sub: `${churnCounts.high} conversations`, color: churnCounts.high > 0 ? 'var(--red)' : 'var(--green)' },
            ].map(({ label, value, sub, color }) => (
              <div key={label} style={{ textAlign: 'center', padding: '4px 0' }}>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>{label}</div>
                <div style={{ fontSize: 26, fontWeight: 800, color, lineHeight: 1 }}>{value}</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>{sub}</div>
              </div>
            ))}
          </div>

          {/* Charts Row */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            <div className="card">
              <div className="card-header"><span className="card-title">Resolution Distribution</span></div>
              <DonutChart data={resolutionData} size={110} />
            </div>
            <div className="card">
              <div className="card-header"><span className="card-title">Churn Risk Distribution</span></div>
              <DonutChart data={churnData} size={110} />
            </div>
          </div>

          {/* Call Reasons */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">Top Call Reasons</span>
              {reasonData.length > 0 && <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{reasonData.length} categories</span>}
            </div>
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
