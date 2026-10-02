import { useEffect, useState } from 'react';
import { api } from '../api';
import { Activity, AlertTriangle, CheckCircle, ClipboardList, PhoneCall, TrendingUp } from 'lucide-react';

const REFRESH_MS = 30000;

function KpiCard({ label, value, sub, icon: Icon, color }) {
  return (
    <div className="kpi-card">
      <div className="kpi-icon" style={{ background: `${color}22` }}>
        <Icon size={16} color={color} />
      </div>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value" style={{ color }}>{value ?? '—'}</div>
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  );
}

export default function Dashboard() {
  const [convs, setConvs] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try {
      const data = await api.getConversations(100);
      setConvs(data);
    } catch { /* handled by api client */ }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); const t = setInterval(load, REFRESH_MS); return () => clearInterval(t); }, []);

  const total = convs.length;
  const ended = convs.filter(c => c.status === 'ended').length;
  const analyzed = convs.filter(c => c.analysis_version > 0).length;
  const pending = ended - analyzed;

  const kpis = [
    { label: 'Conversations', value: total, icon: PhoneCall, color: 'var(--accent)' },
    { label: 'Analyzed', value: analyzed, icon: CheckCircle, color: 'var(--green)', sub: `${pending} pending` },
    { label: 'Active', value: convs.filter(c => c.status === 'active').length, icon: Activity, color: 'var(--amber)' },
    { label: 'Resolution Rate', value: analyzed ? `${Math.round((convs.filter(c => c.analysis_version > 0).length / analyzed) * 100)}%` : '—', icon: TrendingUp, color: 'var(--purple)' },
  ];

  return (
    <div className="page">
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: 20, fontWeight: 700 }}>Overview</h2>
        <p style={{ color: 'var(--text-muted)', fontSize: 13, marginTop: 4 }}>
          Live dashboard — auto-refreshes every 30s
        </p>
      </div>

      <div className="kpi-grid">
        {kpis.map(k => <KpiCard key={k.label} {...k} />)}
      </div>

      <div className="card">
        <div className="card-header">
          <span className="card-title">Recent Conversations</span>
          <button className="btn btn-ghost btn-sm" onClick={load}>Refresh</button>
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
                  <th>Turns</th><th>Version</th><th>Started</th>
                </tr>
              </thead>
              <tbody>
                {convs.length === 0 && (
                  <tr><td colSpan={7} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '32px 0' }}>
                    No conversations yet. Use the Live Demo to create one.
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
                    <td style={{ color: 'var(--text-muted)' }}>{new Date(c.started_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function StatusBadge({ status }) {
  const map = { active: 'badge-amber', ended: 'badge-green', created: 'badge-gray' };
  return <span className={`badge ${map[status] || 'badge-gray'}`}>{status}</span>;
}
