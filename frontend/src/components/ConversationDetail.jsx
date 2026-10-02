import { useEffect, useState } from 'react';
import { api } from '../api';
import {
  ArrowLeft, User, Headphones, CheckCircle, XCircle,
  AlertTriangle, Clock, Shield, ChevronDown, ChevronRight
} from 'lucide-react';

const SENTIMENT_COLOR = {
  positive: 'var(--green)', neutral: 'var(--text-muted)',
  frustrated: 'var(--amber)', angry: 'var(--red)',
};

function SentimentDot({ s }) {
  return <span className={`sentiment-dot sentiment-${s}`} title={s} />;
}

function QAItem({ item }) {
  const [open, setOpen] = useState(false);
  const icons = { pass: <CheckCircle size={14} color="var(--green)" />, fail: <XCircle size={14} color="var(--red)" />, not_applicable: <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>N/A</span>, needs_review: <AlertTriangle size={14} color="var(--amber)" /> };
  return (
    <div style={{ borderBottom: '1px solid var(--border-subtle)', paddingBottom: 10, marginBottom: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }} onClick={() => setOpen(o => !o)}>
        {icons[item.result] || icons.needs_review}
        <span style={{ flex: 1, fontSize: 13 }}>{item.item_id?.replace(/_/g, ' ')}</span>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{(item.confidence * 100).toFixed(0)}%</span>
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
      </div>
      {open && (
        <div style={{ marginTop: 8, paddingLeft: 24 }}>
          <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>{item.explanation}</p>
          {item.quote && (
            <blockquote style={{ borderLeft: '2px solid var(--accent)', paddingLeft: 10, fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic' }}>
              "{item.quote}"
            </blockquote>
          )}
          {item.finding_type && <span className="badge badge-red" style={{ marginTop: 6 }}>{item.finding_type}</span>}
          {item.human_review_required && <span className="badge badge-amber" style={{ marginTop: 6, marginLeft: 4 }}>Review Required</span>}
        </div>
      )}
    </div>
  );
}

export default function ConversationDetail({ convId }) {
  const [conv, setConv] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisMsg, setAnalysisMsg] = useState('');

  useEffect(() => {
    api.getConversation(convId).then(d => { setConv(d); setLoading(false); });
    fetchAnalysis();
  }, [convId]);

  const fetchAnalysis = async () => {
    setAnalysisLoading(true);
    try {
      const a = await api.getAnalysis(convId);
      setAnalysis(a);
    } catch (err) {
      setAnalysisMsg(err.message || 'Analysis pending');
    } finally { setAnalysisLoading(false); }
  };

  if (loading) return <div className="page"><div className="skeleton" style={{ height: 200 }} /></div>;
  if (!conv) return <div className="page"><p>Conversation not found.</p></div>;

  const qa = analysis?.qa_result;
  const scoreColor = qa?.score >= 80 ? 'var(--green)' : qa?.score >= 60 ? 'var(--amber)' : 'var(--red)';

  return (
    <div className="page">
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <button className="btn btn-ghost btn-sm" onClick={() => { window.location.hash = '#/'; }}>
          <ArrowLeft size={14} /> Back
        </button>
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 700 }}>
            Conversation <code style={{ fontSize: 14, background: 'var(--bg-secondary)', padding: '2px 6px', borderRadius: 4 }}>{conv.id.slice(0, 8)}</code>
          </h2>
          <div style={{ display: 'flex', gap: 10, marginTop: 4, alignItems: 'center' }}>
            <span className={`badge ${conv.status === 'ended' ? 'badge-green' : 'badge-amber'}`}>{conv.status}</span>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{conv.turn_count} turns</span>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{new Date(conv.started_at).toLocaleString()}</span>
            {conv.synthetic_assignment && <span className="synthetic-label">Synthetic Assignment</span>}
          </div>
        </div>
      </div>

      <div className="grid-2" style={{ marginBottom: 16 }}>
        {/* Transcript */}
        <div className="card" style={{ maxHeight: 520, overflowY: 'auto' }}>
          <div className="card-header"><span className="card-title">Transcript</span></div>
          <div className="transcript">
            {conv.turns.map(t => (
              <div key={t.turn_id} className={`turn turn-${t.speaker}`}>
                <div className="turn-avatar">
                  {t.speaker === 'agent' ? <Headphones size={12} /> : <User size={12} />}
                </div>
                <div className="turn-body">
                  <div className="turn-meta">
                    <strong style={{ textTransform: 'capitalize' }}>{t.speaker}</strong>
                    <span>{t.turn_id}</span>
                    {t.timestamp && <span>{new Date(t.timestamp).toLocaleTimeString()}</span>}
                  </div>
                  <div className="turn-text">{t.text_redacted}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Analysis Panel */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Summary */}
          {analysis ? (
            <>
              <div className="card">
                <div className="card-header"><span className="card-title">Analysis</span>
                  <span className={`badge ${analysis.provisional ? 'badge-amber' : 'badge-green'}`}>
                    {analysis.provisional ? 'Provisional' : `v${analysis.version}`}
                  </span>
                </div>
                <p style={{ fontSize: 13, lineHeight: 1.7, color: 'var(--text-secondary)', marginBottom: 12 }}>{analysis.summary}</p>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
                  {analysis.reasons.map(r => <span key={r} className="badge badge-blue">{r.replace(/_/g, ' ')}</span>)}
                </div>
                <div style={{ display: 'flex', gap: 16 }}>
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 2 }}>RESOLUTION</div>
                    <ResolutionBadge r={analysis.resolution} />
                  </div>
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 2 }}>CHURN RISK</div>
                    <ChurnBadge r={analysis.churn_risk} />
                  </div>
                  {analysis.false_resolution && (
                    <div><div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 2 }}>FALSE RESOLUTION</div>
                      <span className="badge badge-red"><AlertTriangle size={10} /> Detected</span></div>
                  )}
                </div>
                {analysis.churn_signals?.length > 0 && (
                  <div style={{ marginTop: 12, padding: '8px 12px', background: 'var(--red-bg)', borderRadius: 6 }}>
                    <div style={{ fontSize: 11, color: 'var(--red)', fontWeight: 600, marginBottom: 4 }}>Churn Signals</div>
                    {analysis.churn_signals.map((s, i) => <div key={i} style={{ fontSize: 12, color: 'var(--text-secondary)' }}>• {s}</div>)}
                  </div>
                )}
              </div>

              {/* QA Result */}
              {qa && (
                <div className="card">
                  <div className="card-header">
                    <span className="card-title">QA Score</span>
                    {qa.critical_violation && <span className="badge badge-red"><Shield size={10} /> Critical Violation</span>}
                  </div>
                  <div style={{ display: 'flex', gap: 20, alignItems: 'center', marginBottom: 16 }}>
                    <div className="score-circle" style={{ background: `${scoreColor}22`, color: scoreColor }}>
                      {qa.score != null ? `${qa.score}` : '—'}
                    </div>
                    <div style={{ flex: 1 }}>
                      <div className="qa-bar-wrap">
                        <div className="qa-bar">
                          <div className="qa-bar-fill" style={{ width: `${(qa.coverage * 100).toFixed(0)}%`, background: qa.coverage >= 0.7 ? 'var(--green)' : 'var(--amber)' }} />
                        </div>
                        <span style={{ fontSize: 11, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                          {(qa.coverage * 100).toFixed(0)}% coverage
                        </span>
                      </div>
                      {qa.score_label === 'partial' && (
                        <div style={{ fontSize: 11, color: 'var(--amber)', marginTop: 4 }}>Score is partial — coverage below 70%</div>
                      )}
                      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                        {qa.items_assessed}/{qa.items_applicable} items assessed · {qa.items_needs_review} needs review
                      </div>
                    </div>
                  </div>
                  {qa.items?.map(item => <QAItem key={item.item_id} item={item} />)}
                </div>
              )}
            </>
          ) : (
            <div className="card" style={{ textAlign: 'center', padding: 40 }}>
              {analysisLoading
                ? <><Clock size={24} style={{ color: 'var(--text-muted)', marginBottom: 8 }} /><p style={{ color: 'var(--text-muted)' }}>Loading analysis…</p></>
                : <><Clock size={24} style={{ color: 'var(--text-muted)', marginBottom: 8 }} />
                  <p style={{ color: 'var(--text-muted)', marginBottom: 12 }}>{analysisMsg || 'Analysis not yet available'}</p>
                  <button className="btn btn-ghost btn-sm" onClick={fetchAnalysis}>Check again</button></>
              }
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ResolutionBadge({ r }) {
  const map = { resolved: 'badge-green', partially_resolved: 'badge-amber', unresolved: 'badge-red', pending: 'badge-amber', escalated: 'badge-purple', unknown: 'badge-gray' };
  return <span className={`badge ${map[r] || 'badge-gray'}`}>{r?.replace(/_/g, ' ')}</span>;
}

function ChurnBadge({ r }) {
  const map = { low: 'badge-green', medium: 'badge-amber', high: 'badge-red' };
  return <span className={`badge ${map[r] || 'badge-gray'}`}>{r} risk</span>;
}
