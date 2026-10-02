import { useEffect, useState, useCallback } from 'react';
import { api } from '../api';
import {
  Activity, AlertTriangle, CheckCircle, PhoneCall,
  TrendingUp, Clock, ShieldAlert, RefreshCw,
} from 'lucide-react';

const REFRESH_MS = 30000;

function KpiCard({ label, value, sub, icon: Icon, color, onClick }) {
  return (
    <div className="kpi-card" onClick={onClick} style={onClick ? { cursor: 'pointer' } : {}}>
      <div className="kpi-icon" style={{ background: `${color}22` }}>
        <Icon size={16} color={color} />
      </div>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value" style={{ color }}>{value ?? '—'}</div>
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  );
}

function StatusBadge({ status }) {
  const map = { active: 'badge-amber', ended: 'badge-green', created: 'badge-gray' };
  return <span className={`badge ${map[status] || 'badge-gray'}`}>{status}</span>;
}

function RiskBadge({ risk }) {
  if (!risk) return null;
  const map = { high: 'badge-red', medium: 'badge-amber', low: 'badge-green' };
  return <span className={`badge ${map[risk] || 'badge-gray'}`}>{risk}</span>;
}

function ScoreBar({ score }) {
  if (score == null) return <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>—</span>;
  const color = score >= 80 ? 'var(--green)' : score >= 60 ? 'var(--amber)' : 'var(--red)';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{ flex: 1, height: 4, background: 'var(--border)', borderRadius: 2 }}>
        <div style={{ width: `${score}%`, height: '100%', background: color, borderRadius: 2, transition: 'width 0.4s' }} />
      </div>
      <span style={{ fontSize: 11, color, minWidth: 28 }}>{score}</span>
    </div>
  );
}

export default function Dashboard() {
  const [convs, setConvs] = useState([]);
  const [openCommitments, setOpenCommitments] = useState([]);
  const [falseResolutions, setFalseResolutions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState('convs'); // 'convs' | 'commitments' | 'alerts'
  const [statusFilter, setStatusFilter] = useState('');

  const load = useCallback(async (showRefresh = false) => {
    if (showRefresh) setRefreshing(true);
    try {
      const [data, commits, falseRes] = await Promise.allSettled([
        api.getConversations(100, 0, statusFilter),
        api.getOpenCommitments(50),
        api.getFalseResolutions(),
      ]);
      if (data.status === 'fulfilled') setConvs(data.value);
      if (commits.status === 'fulfilled') setOpenCommitments(commits.value);
      if (falseRes.status === 'fulfilled') setFalseResolutions(falseRes.value);
    } catch { /* handled by api client */ }
    finally { setLoading(false); setRefreshing(false); }
  }, [statusFilter]);

  useEffect(() => {
    load();
    const t = setInterval(() => load(), REFRESH_MS);
    return () => clearInterval(t);
  }, [load]);

  const total = convs.length;
  const ended = convs.filter(c => c.status === 'ended').length;
  const analyzed = convs.filter(c => c.analysis_version > 0).length;
  const active = convs.filter(c => c.status === 'active').length;

  // QA average from conversations that have analysis (use qa_score field if returned)
  const scored = convs.filter(c => c.qa_score != null);
  const avgScore = scored.length ? Math.round(scored.reduce((s, c) => s + c.qa_score, 0) / scored.length) : null;

  const kpis = [
    { label: 'Total Conversations', value: total, icon: PhoneCall, color: 'var(--accent)', sub: `${active} active` },
    { label: 'Analyzed', value: analyzed, icon: CheckCircle, color: 'var(--green)', sub: `${ended - analyzed} pending` },
    { label: 'Open Commitments', value: openCommitments.length, icon: Clock, color: 'var(--amber)',
      onClick: () => setActiveTab('commitments'), sub: 'click to view' },
    { label: 'False Resolutions', value: falseResolutions.length, icon: ShieldAlert, color: 'var(--red)',
      onClick: () => setActiveTab('alerts'), sub: 'click to view' },
    ...(avgScore != null ? [{ label: 'Avg QA Score', value: avgScore, icon: TrendingUp, color: 'var(--purple)', sub: `across ${scored.length} analyzed` }] : []),
  ];

  return (
    <div className="page">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <div>
          <h2 style={{ fontSize: 20, fontWeight: 700 }}>Overview</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: 13, marginTop: 4 }}>
            Auto-refreshes every 30s
          </p>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={() => load(true)} disabled={refreshing}
          style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <RefreshCw size={13} style={{ animation: refreshing ? 'spin 1s linear infinite' : 'none' }} />
          {refreshing ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      <div className="kpi-grid">
        {kpis.map(k => <KpiCard key={k.label} {...k} />)}
      </div>

      {/* Tab bar */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 12, borderBottom: '1px solid var(--border)', paddingBottom: 0 }}>
        {[
          { id: 'convs', label: `Conversations (${total})` },
          { id: 'commitments', label: `Open Commitments (${openCommitments.length})` },
          { id: 'alerts', label: `False Resolutions (${falseResolutions.length})` },
        ].map(tab => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)}
            style={{
              padding: '8px 14px', fontSize: 13, fontWeight: activeTab === tab.id ? 600 : 400,
              background: 'none', border: 'none', cursor: 'pointer',
              color: activeTab === tab.id ? 'var(--accent)' : 'var(--text-muted)',
              borderBottom: activeTab === tab.id ? '2px solid var(--accent)' : '2px solid transparent',
              marginBottom: -1,
            }}>
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'convs' && (
        <div className="card">
          <div className="card-header">
            <span className="card-title">Conversations</span>
            <div style={{ display: 'flex', gap: 8 }}>
              {['', 'active', 'ended'].map(s => (
                <button key={s || 'all'} className={`btn btn-sm ${statusFilter === s ? 'btn-primary' : 'btn-ghost'}`}
                  onClick={() => setStatusFilter(s)}>
                  {s || 'All'}
                </button>
              ))}
            </div>
          </div>
          {loading ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {[...Array(5)].map((_, i) => <div key={i} className="skeleton" style={{ height: 40 }} />)}
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>ID</th><th>Agent</th><th>Team</th><th>Status</th>
                    <th>Turns</th><th>Analysis</th><th>QA Score</th><th>Risk</th><th>Started</th>
                  </tr>
                </thead>
                <tbody>
                  {convs.length === 0 && (
                    <tr><td colSpan={9} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '32px 0' }}>
                      No conversations. Use the Live Demo to create one.
                    </td></tr>
                  )}
                  {convs.map(c => (
                    <tr key={c.id} style={{ cursor: 'pointer' }}
                        onClick={() => window.location.hash = `#/conversation/${c.id}`}>
                      <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{c.id.slice(0, 8)}…</td>
                      <td>
                        {c.agent_id ?? '—'}
                        {c.synthetic_assignment && <span className="synthetic-label" style={{ marginLeft: 6 }}>SYN</span>}
                      </td>
                      <td>{c.team_id ?? '—'}</td>
                      <td><StatusBadge status={c.status} /></td>
                      <td>{c.turn_count}</td>
                      <td>{c.analysis_version > 0 ? `v${c.analysis_version}` : <span style={{ color: 'var(--text-muted)' }}>—</span>}</td>
                      <td style={{ minWidth: 100 }}><ScoreBar score={c.qa_score} /></td>
                      <td><RiskBadge risk={c.churn_risk} /></td>
                      <td style={{ color: 'var(--text-muted)', fontSize: 12 }}>{new Date(c.started_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {activeTab === 'commitments' && (
        <div className="card">
          <div className="card-header"><span className="card-title">Open Commitments</span></div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Conv</th><th>Description</th><th>Owner</th><th>Deadline</th><th>Status</th></tr></thead>
              <tbody>
                {openCommitments.length === 0 && (
                  <tr><td colSpan={5} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '32px 0' }}>
                    No open commitments.
                  </td></tr>
                )}
                {openCommitments.map((c, i) => (
                  <tr key={i} style={{ cursor: 'pointer' }}
                      onClick={() => c.conversation_id && (window.location.hash = `#/conversation/${c.conversation_id}`)}>
                    <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{(c.conversation_id || '').slice(0, 8)}…</td>
                    <td>{c.description}</td>
                    <td>{c.owner || '—'}</td>
                    <td style={{ color: c.deadline_flag === 'overdue' ? 'var(--red)' : 'inherit' }}>
                      {c.deadline || '—'}{c.deadline_flag === 'overdue' && ' ⚠'}
                    </td>
                    <td><span className="badge badge-amber">{c.status}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === 'alerts' && (
        <div className="card">
          <div className="card-header"><span className="card-title">False Resolutions</span></div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Conv</th><th>Agent</th><th>Reason</th><th>Ended</th></tr></thead>
              <tbody>
                {falseResolutions.length === 0 && (
                  <tr><td colSpan={4} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '32px 0' }}>
                    No false resolutions detected.
                  </td></tr>
                )}
                {falseResolutions.map((c, i) => (
                  <tr key={i} style={{ cursor: 'pointer' }}
                      onClick={() => c.id && (window.location.hash = `#/conversation/${c.id}`)}>
                    <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{(c.id || '').slice(0, 8)}…</td>
                    <td>{c.agent_id || '—'}</td>
                    <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>{c.false_resolution_reason || '—'}</td>
                    <td style={{ color: 'var(--text-muted)', fontSize: 12 }}>{c.ended_at ? new Date(c.ended_at).toLocaleString() : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
