import { useEffect, useState, useCallback } from 'react';
import { api } from '../api';
import {
  ArrowLeft, User, Headphones, CheckCircle, XCircle,
  AlertTriangle, Clock, Shield, ChevronDown, ChevronRight, RefreshCw,
} from 'lucide-react';
import LiveAppendPanel from './LiveAppendPanel';

const SENTIMENT_COLOR = {
  positive: 'var(--green)', neutral: 'var(--text-muted)',
  frustrated: 'var(--amber)', angry: 'var(--red)',
};

function SentimentDot({ s }) {
  return <span style={{ width: 8, height: 8, borderRadius: '50%', background: SENTIMENT_COLOR[s] || 'var(--text-muted)', display: 'inline-block', flexShrink: 0 }} title={s} />;
}

function QAItem({ item }) {
  const [open, setOpen] = useState(false);
  const icons = {
    pass: <CheckCircle size={14} color="var(--green)" />,
    fail: <XCircle size={14} color="var(--red)" />,
    not_applicable: <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>N/A</span>,
    needs_review: <AlertTriangle size={14} color="var(--amber)" />,
  };
  // D9: only show verification badge for items that were actually verified (not N/A)
  const isNA = item.result === 'not_applicable';
  return (
    <div style={{ borderBottom: '1px solid var(--border-subtle)', paddingBottom: 10, marginBottom: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }} onClick={() => setOpen(o => !o)}>
        {icons[item.result] || icons.needs_review}
        <span style={{ flex: 1, fontSize: 13 }}>{(item.display || item.item_id)?.replace(/_/g, ' ')}</span>
        {!isNA && <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{((item.confidence || 0) * 100).toFixed(0)}%</span>}
        {/* D9: only show verification badge for verified items, not N/A */}
        {!isNA && item.verification_result && (
          <span style={{ fontSize: 10, padding: '1px 5px', borderRadius: 3,
            background: item.verification_result === 'supported' ? 'var(--green-bg)' : item.verification_result === 'not_supported' ? 'var(--red-bg)' : 'var(--amber-bg)',
            color: item.verification_result === 'supported' ? 'var(--green)' : item.verification_result === 'not_supported' ? 'var(--red)' : 'var(--amber)',
          }}>verified: {item.verification_result}</span>
        )}
        {isNA && item.explanation && (
          <span style={{ fontSize: 10, color: 'var(--text-muted)', fontStyle: 'italic', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
            title={item.explanation}>not applicable</span>
        )}
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
      </div>
      {open && (
        <div style={{ marginTop: 8, paddingLeft: 24 }}>
          <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>{item.explanation}</p>
          {!isNA && (item.quote || (item.evidence || []).map(e => e.quote).join(' ')) && (
            <blockquote style={{ borderLeft: '2px solid var(--accent)', paddingLeft: 10, fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic' }}>
              "{item.quote || (item.evidence || []).map(e => e.quote).join(' | ')}"
            </blockquote>
          )}
          {item.finding_type && <span className="badge badge-red" style={{ marginTop: 6 }}>{item.finding_type}</span>}
          {item.human_review_required && <span className="badge badge-amber" style={{ marginTop: 6, marginLeft: 4 }}>Review Required</span>}
        </div>
      )}
    </div>
  );
}

function SentimentTimeline({ trajectory }) {
  if (!trajectory || trajectory.length === 0) return null;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 3, flexWrap: 'wrap', padding: '8px 0' }}>
      {trajectory.map((pt, i) => (
        <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
          <SentimentDot s={pt.sentiment} />
          <span style={{ fontSize: 9, color: 'var(--text-muted)' }}>{pt.turn_id?.replace('turn_', '')}</span>
        </div>
      ))}
    </div>
  );
}

// D6: Convert raw deadline tags/phrases to human-readable text
function formatDeadline(raw) {
  if (!raw) return null;
  const lower = raw.toLowerCase().trim();
  // Strip internal tag-like tokens
  if (lower === 'eod' || lower === 'end of day') return 'End of day';
  if (lower === 'immediate' || lower === 'asap') return 'Immediately';
  if (lower === 'tomorrow') return 'Tomorrow';
  if (lower === 'specific' || lower === 'explicit') return raw; // show original if just tag
  // Remove tag prefixes like "[eod]", "[specific]" etc.
  const cleaned = raw.replace(/^\[?(eod|specific|explicit|immediate|asap)\]?\s*/i, '').trim();
  // If it looks like a time "6pm", "18:00" — keep as is
  if (/^\d{1,2}(:\d{2})?\s*(am|pm)?$/i.test(cleaned)) return cleaned;
  return cleaned || raw;
}

function CommitmentLedger({ commitments }) {
  if (!commitments || commitments.length === 0) return (
    <p style={{ fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic' }}>No commitments recorded.</p>
  );
  const statusColors = {
    proposed: 'badge-amber', accepted: 'badge-blue', scheduled: 'badge-blue',
    completed: 'badge-green', cancelled: 'badge-gray', uncertain: 'badge-amber',
  };
  return (
    <div>
      {commitments.map((c, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
          <span className={`badge ${statusColors[c.status] || 'badge-gray'}`}>{c.status}</span>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 13, color: 'var(--text-primary)', marginBottom: 2 }}>{c.description}</div>
            <div style={{ display: 'flex', gap: 10, fontSize: 11, color: 'var(--text-muted)' }}>
              {c.owner && <span>Owner: {c.owner}</span>}
              {c.deadline && (
                <span style={{ color: 'var(--amber)' }} title={c.deadline}>
                  Due: {formatDeadline(c.deadline)}
                </span>
              )}
              {c.created_at_turn_id && <span>Created at: {c.created_at_turn_id}</span>}
            </div>
            {(c.evidence_json || []).map((ev, ei) => ev.quote && (
              <blockquote key={ei} style={{ borderLeft: '2px solid var(--border-subtle)', paddingLeft: 8, fontSize: 11, color: 'var(--text-muted)', fontStyle: 'italic', margin: '4px 0' }}>
                "{ev.quote}"
              </blockquote>
            ))}
          </div>
          {c.provisional && <span className="badge badge-amber" style={{ fontSize: 10 }}>provisional</span>}
        </div>
      ))}
    </div>
  );
}

export default function ConversationDetail({ convId }) {
  const [conv, setConv] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState('transcript');
  const [highlightTurn, setHighlightTurn] = useState(null);

  // Version picker
  const [versions, setVersions] = useState([]);
  const [selectedVersion, setSelectedVersion] = useState(null);
  const [versionAnalysis, setVersionAnalysis] = useState(null);

  // Reviewer workflow
  const [reviews, setReviews] = useState([]);
  const [reviewVerdict, setReviewVerdict] = useState(''); // D12: no default; user must choose
  const [reviewNotes, setReviewNotes] = useState('');
  const [reviewSubmitting, setReviewSubmitting] = useState(false);
  const [reviewMsg, setReviewMsg] = useState('');
  const [reopening, setReopening] = useState(false);
  const [ending, setEnding] = useState(false);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    else setRefreshing(true);
    try {
      const d = await api.getConversation(convId);
      setConv(d);
      setError('');
    } catch (err) {
      setError(err.message || 'Failed to load conversation');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [convId]);

  useEffect(() => { load(); }, [load]);

  // Load analysis versions when conv is ended
  useEffect(() => {
    if (!conv || conv.status !== 'ended') return;
    api.getAnalysisVersions(convId).then(setVersions).catch(() => {});
    api.getReviews(convId).then(setReviews).catch(() => {});
  }, [conv, convId]);

  // Load specific version when selected
  useEffect(() => {
    if (selectedVersion == null) { setVersionAnalysis(null); return; }
    api.getAnalysis(convId, selectedVersion).then(setVersionAnalysis).catch(() => setVersionAnalysis(null));
  }, [selectedVersion, convId]);

  // Auto-refresh if ended but analysis pending
  useEffect(() => {
    if (!conv) return;
    if (conv.status === 'ended' && !conv.analysis) {
      const t = setInterval(() => load(true), 15000);
      return () => clearInterval(t);
    }
  }, [conv, load]);

  if (loading) return <div className="page"><div className="skeleton" style={{ height: 200 }} /></div>;
  if (error) return <div className="page"><div className="error-banner">{error}</div></div>;
  if (!conv) return <div className="page"><p>Conversation not found.</p></div>;

  const analysis = conv.analysis;
  const displayAnalysis = versionAnalysis || analysis;
  const qa = displayAnalysis?.qa_result;
  const scoreColor = !qa?.score ? 'var(--text-muted)' : qa.score >= 80 ? 'var(--green)' : qa.score >= 60 ? 'var(--amber)' : 'var(--red)';
  const isActive = conv.status === 'active' || conv.status === 'created';

  const scrollToTurn = (turnId) => {
    setHighlightTurn(turnId);
    setActiveTab('transcript');
    setTimeout(() => {
      const el = document.getElementById(`turn-${turnId}`);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      setTimeout(() => setHighlightTurn(null), 2500);
    }, 100);
  };

  const TABS = [
    ['transcript', 'Transcript'],
    ...(isActive ? [['live', 'Live Panel']] : []),
    ['analysis', 'Analysis'],
    ['qa', 'QA'],
    ['commitments', 'Commitments'],
    ...(!isActive ? [['reviewer', 'Reviewer']] : []),
  ];

  const handleReopen = async () => {
    if (!confirm('Reopen this conversation? Prior analysis will be preserved.')) return;
    setReopening(true);
    try {
      await api.reopenConversation(convId);
      await load();
      setActiveTab('live');
    } catch (e) {
      alert(e.message);
    } finally {
      setReopening(false);
    }
  };

  const handleEnd = async () => {
    if (!confirm('End this conversation and queue analysis?')) return;
    setEnding(true);
    try {
      await api.endConversation(convId);
      await load();
    } catch (e) {
      alert(e.message);
    } finally {
      setEnding(false);
    }
  };

  const handleClose = async () => {
    if (!confirm('Permanently close this conversation? It will no longer be possible to reopen it.')) return;
    try {
      await api.closeConversation(convId);
      await load();
    } catch (e) {
      alert(e.message);
    }
  };

  const submitReview = async () => {
    if (!reviewVerdict) { setReviewMsg('Error: Please select a verdict.'); return; }
    setReviewSubmitting(true);
    setReviewMsg('');
    try {
      await api.createReview(convId, reviewVerdict, reviewNotes);
      setReviewMsg('Review submitted.');
      setReviewNotes('');
      setReviewVerdict('');
      const updated = await api.getReviews(convId);
      setReviews(updated);
    } catch (e) {
      setReviewMsg(`Error: ${e.message}`);
    } finally {
      setReviewSubmitting(false);
    }
  };

  return (
    <div className="page">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <button className="btn btn-ghost btn-sm" onClick={() => { window.location.hash = '#/?tab=conversations'; }}>
          <ArrowLeft size={14} /> Back
        </button>
        <div style={{ flex: 1 }}>
          <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>
            Conversation <code style={{ fontSize: 14, background: 'var(--bg-secondary)', padding: '2px 6px', borderRadius: 4 }}>{conv.id.slice(0, 8)}</code>
          </h2>
          <div style={{ display: 'flex', gap: 10, marginTop: 4, alignItems: 'center', flexWrap: 'wrap' }}>
            <span className={`badge ${conv.status === 'ended' ? 'badge-green' : conv.status === 'active' ? 'badge-amber' : conv.status === 'closed' ? 'badge-gray' : 'badge-blue'}`}>{conv.status}</span>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{conv.turn_count} turns</span>
            {conv.started_at && (
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                {new Date(conv.started_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
                {', '}
                {new Date(conv.started_at).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}
              </span>
            )}
            {conv.agent_id && <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Agent: <strong>{conv.agent_id}</strong></span>}
            {conv.team_id && <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Team: <strong>{conv.team_id}</strong></span>}
            {conv.synthetic_assignment && <span className="synthetic-label">Synthetic Assignment</span>}
          </div>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={() => load(true)} disabled={refreshing}
          style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <RefreshCw size={13} style={{ animation: refreshing ? 'spin 1s linear infinite' : 'none' }} />
          {refreshing ? 'Refreshing…' : 'Refresh'}
        </button>
        {conv.status === 'ended' && (
          <>
            <button className="btn btn-ghost btn-sm" onClick={handleReopen} disabled={reopening}
              style={{ color: 'var(--amber)', display: 'flex', alignItems: 'center', gap: 6 }}>
              {reopening ? 'Reopening…' : 'Reopen'}
            </button>
            <button className="btn btn-ghost btn-sm" onClick={handleClose}
              style={{ color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 6 }}>
              Close
            </button>
          </>
        )}
        {conv.status === 'active' && (
          <button className="btn btn-ghost btn-sm" onClick={handleEnd} disabled={ending}
            style={{ color: 'var(--red)', display: 'flex', alignItems: 'center', gap: 6 }}>
            {ending ? 'Ending…' : 'End Conversation'}
          </button>
        )}
        {versions.length > 1 && (
          <select value={selectedVersion ?? ''} onChange={e => setSelectedVersion(e.target.value ? Number(e.target.value) : null)}
            title="Select analysis version"
            style={{ fontSize: 12, background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: 4, padding: '4px 8px', color: 'var(--text-primary)' }}>
            <option value="">Latest (v{versions[0]?.version})</option>
            {versions.map(v => (
              <option key={v.version} value={v.version}>v{v.version} — {v.resolution} {v.provisional ? '(provisional)' : ''}</option>
            ))}
          </select>
        )}
      </div>

      {/* Sub-tabs — uses design system .tabs / .tab-btn */}
      <div className="tabs">
        {TABS.map(([id, label]) => (
          <button key={id} className={`tab-btn${activeTab === id ? ' active' : ''}`}
            onClick={() => setActiveTab(id)}>
            {label}
          </button>
        ))}
      </div>

      {/* ---- TRANSCRIPT TAB ---- */}
      {activeTab === 'transcript' && (
        <div className="card" style={{ maxHeight: 640, overflowY: 'auto', padding: '16px' }}>
          <div className="card-header" style={{ marginBottom: 14 }}>
            <span className="card-title">Transcript</span>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{(conv.turns || []).length} turns</span>
          </div>
          <div className="transcript">
            {(conv.turns || []).map(t => (
              <div key={t.turn_id} id={`turn-${t.turn_id}`}
                className={`turn turn-${t.speaker}${highlightTurn === t.turn_id ? ' highlighted' : ''}`}
                style={{ borderRadius: 8, padding: '4px 0', transition: 'all 0.25s' }}>
                <div className="turn-avatar">
                  {t.speaker === 'agent' ? <Headphones size={12} /> : <User size={12} />}
                </div>
                <div className="turn-body">
                  <div className="turn-meta">
                    <strong style={{ textTransform: 'capitalize', color: t.speaker === 'agent' ? 'var(--accent-hover)' : 'var(--purple)', fontSize: 12 }}>{t.speaker}</strong>
                    <code style={{ fontSize: 10, background: 'transparent', color: 'var(--text-muted)', padding: 0 }}>{t.turn_id}</code>
                    {t.timestamp && <span style={{ fontSize: 10 }}>{new Date(t.timestamp).toLocaleTimeString()}</span>}
                  </div>
                  <div className="turn-text">{t.text_redacted}</div>
                </div>
              </div>
            ))}
            {(conv.turns || []).length === 0 && (
              <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--text-muted)' }}>
                <Clock size={24} style={{ marginBottom: 8, opacity: 0.5 }} />
                <p style={{ fontSize: 13 }}>No turns recorded yet.</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ---- LIVE PANEL TAB ---- */}
      {activeTab === 'live' && isActive && (
        <LiveAppendPanel conv={conv} onTurnAdded={() => load(true)} />
      )}

      {/* ---- ANALYSIS TAB ---- */}
      {activeTab === 'analysis' && (() => {
        return displayAnalysis ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {selectedVersion != null && (
              <div className="card" style={{ padding: '8px 14px', background: 'var(--amber-bg)', borderRadius: 6 }}>
                <span style={{ fontSize: 12, color: 'var(--amber)' }}>Viewing historical version v{selectedVersion}. Select "Latest" to return to current analysis.</span>
              </div>
            )}
            {/* Summary */}
            <div className="card">
              <div className="card-header">
                <span className="card-title">Analysis</span>
                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <span className={`badge ${displayAnalysis.provisional ? 'badge-amber' : 'badge-green'}`}>
                    {displayAnalysis.provisional ? 'Provisional' : `v${displayAnalysis.version}`}
                  </span>
                  {displayAnalysis.model && (
                    <span style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'monospace' }}>{displayAnalysis.model}</span>
                  )}
                </div>
              </div>

              {/* Summary text */}
              <p style={{ fontSize: 13, lineHeight: 1.75, color: 'var(--text-secondary)', marginBottom: 14,
                padding: '10px 14px', background: 'var(--bg-secondary)', borderRadius: 8,
                borderLeft: '3px solid var(--accent-border)' }}>
                {displayAnalysis.summary}
              </p>

              {/* Call reasons */}
              {(displayAnalysis.reasons || []).length > 0 && (
                <div className="insight-row">
                  <span className="insight-label">Call Reasons</span>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {(displayAnalysis.reasons || []).map(r => <span key={r} className="reason-chip">{r.replace(/_/g, ' ')}</span>)}
                  </div>
                </div>
              )}

              {/* Resolution / Churn / False Resolution */}
              <div className="insight-row">
                <span className="insight-label">Resolution</span>
                <span className={`badge ${displayAnalysis.resolution === 'resolved' ? 'badge-green' : displayAnalysis.resolution === 'unresolved' ? 'badge-red' : 'badge-amber'}`}>
                  {displayAnalysis.resolution?.replace(/_/g, ' ')}
                </span>
              </div>
              {displayAnalysis.churn_risk && (
                <div className="insight-row">
                  <span className="insight-label">Churn Risk</span>
                  <span className={`badge ${displayAnalysis.churn_risk === 'high' ? 'badge-red' : displayAnalysis.churn_risk === 'medium' ? 'badge-amber' : 'badge-green'}`}>
                    {displayAnalysis.churn_risk} risk
                  </span>
                </div>
              )}
              {displayAnalysis.false_resolution && (
                <div className="insight-row">
                  <span className="insight-label">False Resolution</span>
                  <span className="badge badge-red"><AlertTriangle size={10} /> Detected</span>
                </div>
              )}
              {(displayAnalysis.churn_signals || []).length > 0 && (
                <div style={{ padding: '8px 12px', background: 'var(--red-bg)', borderRadius: 6 }}>
                  <div style={{ fontSize: 11, color: 'var(--red)', fontWeight: 600, marginBottom: 4 }}>Churn Signals</div>
                  {displayAnalysis.churn_signals.map((s, i) => <div key={i} style={{ fontSize: 12, color: 'var(--text-secondary)' }}>• {s}</div>)}
                </div>
              )}
            </div>

            {/* Sentiment timeline */}
            {(displayAnalysis.sentiment_trajectory || []).length > 0 && (
              <div className="card">
                <div className="card-header"><span className="card-title">Sentiment Trajectory</span></div>
                <SentimentTimeline trajectory={displayAnalysis.sentiment_trajectory} />
                <div style={{ display: 'flex', gap: 12, marginTop: 8 }}>
                  {Object.entries(SENTIMENT_COLOR).map(([s, c]) => (
                    <div key={s} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: 'var(--text-muted)' }}>
                      <span style={{ width: 8, height: 8, borderRadius: '50%', background: c, display: 'inline-block' }} />
                      {s}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {displayAnalysis.false_resolution && (
              <div style={{ padding: '12px 16px', background: 'var(--red-bg)', borderRadius: 8, border: '1px solid var(--red)', display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                <AlertTriangle size={16} color="var(--red)" style={{ flexShrink: 0, marginTop: 2 }} />
                <div>
                  <div style={{ fontWeight: 700, color: 'var(--red)', fontSize: 13, marginBottom: 4 }}>False Resolution Detected</div>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{displayAnalysis.false_resolution_reason}</div>
                </div>
              </div>
            )}

            {/* D10: Open commitments summary in analysis tab */}
            {(() => {
              const openComm = (displayAnalysis.commitments || []).filter(
                c => !['completed', 'cancelled'].includes(c.status)
              );
              if (openComm.length === 0) return null;
              return (
                <div className="card">
                  <div className="card-header">
                    <span className="card-title">Open Commitments</span>
                    <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{openComm.length} open</span>
                  </div>
                  <CommitmentLedger commitments={openComm} />
                  {(displayAnalysis.commitments || []).length > openComm.length && (
                    <div style={{ marginTop: 8, fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic' }}>
                      {(displayAnalysis.commitments || []).length - openComm.length} completed / cancelled — visible in the Commitments tab.
                    </div>
                  )}
                </div>
              );
            })()}
          </div>
        ) : (
          <div className="card" style={{ textAlign: 'center', padding: 40 }}>
            <Clock size={24} style={{ color: 'var(--text-muted)', marginBottom: 8 }} />
            <p style={{ color: 'var(--text-muted)', marginBottom: 12 }}>
              {conv.status === 'ended' ? 'Analysis is being processed…' : 'Analysis available after conversation ends.'}
            </p>
            {conv.status === 'ended' && (
              <button className="btn btn-ghost btn-sm" onClick={() => load(true)} disabled={refreshing}>
                {refreshing ? 'Checking…' : 'Check again'}
              </button>
            )}
          </div>
        );
      })()}

      {/* ---- QA TAB ---- */}
      {activeTab === 'qa' && (
        qa ? (
          <div className="card">
            <div className="card-header">
              <span className="card-title">QA Score</span>
              {qa.critical_violation && <span className="badge badge-red"><Shield size={10} /> Critical Violation</span>}
              {qa.score_label === 'partial' && <span className="badge badge-amber">Partial Coverage</span>}
            </div>
            <div style={{ display: 'flex', gap: 20, alignItems: 'center', marginBottom: 16 }}>
              <div className="score-circle" style={{ background: `${scoreColor}22`, color: scoreColor }}>
                {qa.score != null ? `${qa.score}` : '—'}
              </div>
              <div style={{ flex: 1 }}>
                <div className="qa-bar-wrap">
                  <div className="qa-bar">
                    <div className="qa-bar-fill" style={{ width: `${((qa.coverage || 0) * 100).toFixed(0)}%`, background: (qa.coverage || 0) >= 0.7 ? 'var(--green)' : 'var(--amber)' }} />
                  </div>
                  <span style={{ fontSize: 11, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                    {((qa.coverage || 0) * 100).toFixed(0)}% coverage
                  </span>
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                  {qa.items_assessed}/{qa.items_applicable} assessed · {qa.items_needs_review} needs review
                </div>
              </div>
            </div>
            {(qa.items || []).map(item => (
              <QAItem key={item.item_id} item={item} />
            ))}
          </div>
        ) : (
          <div className="card" style={{ textAlign: 'center', padding: 40 }}>
            <p style={{ color: 'var(--text-muted)' }}>QA results available after final analysis.</p>
          </div>
        )
      )}

      {/* ---- COMMITMENTS TAB ---- */}
      {activeTab === 'commitments' && (
        <div className="card">
          <div className="card-header">
            <span className="card-title">Commitment Ledger</span>
            {displayAnalysis ? (
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>From final analysis</span>
            ) : (
              <span style={{ fontSize: 12, color: 'var(--amber)' }}>Provisional</span>
            )}
          </div>
          <CommitmentLedger commitments={displayAnalysis?.commitments || conv.provisional_state?.open_commitments || []} />
        </div>
      )}

      {/* ---- REVIEWER TAB ---- */}
      {activeTab === 'reviewer' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {/* Submit review */}
          <div className="card">
            <div className="card-header"><span className="card-title">Submit Review</span></div>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 10 }}>
              <label style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 600 }}>
                Verdict <span style={{ color: 'var(--red)' }}>*</span>
              </label>
              <select value={reviewVerdict} onChange={e => setReviewVerdict(e.target.value)}
                style={{ fontSize: 13, background: 'var(--bg-secondary)', borderRadius: 4, padding: '5px 10px',
                  border: `1px solid ${!reviewVerdict ? 'var(--amber)' : 'var(--border-subtle)'}`,
                  color: reviewVerdict ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                <option value="" disabled>Select a verdict...</option>
                <option value="approved">Approved</option>
                <option value="rejected">Rejected</option>
                <option value="needs_rework">Needs Rework</option>
              </select>
            </div>
            <textarea value={reviewNotes} onChange={e => setReviewNotes(e.target.value)}
              placeholder="Notes (optional)..."
              rows={3}
              style={{ width: '100%', fontSize: 13, background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: 4, padding: '8px 10px', color: 'var(--text-primary)', resize: 'vertical', boxSizing: 'border-box', marginBottom: 10 }} />
            <button className="btn btn-primary btn-sm" onClick={submitReview}
              disabled={reviewSubmitting || !reviewVerdict}
              title={!reviewVerdict ? 'Please select a verdict before submitting' : ''}>
              {reviewSubmitting ? 'Submitting...' : 'Submit Review'}
            </button>
            {!reviewVerdict && <span style={{ marginLeft: 12, fontSize: 12, color: 'var(--amber)' }}>A verdict is required.</span>}
            {reviewMsg && <span style={{ marginLeft: 12, fontSize: 12, color: reviewMsg.startsWith('Error') ? 'var(--red)' : 'var(--green)' }}>{reviewMsg}</span>}
          </div>

          {/* Review history */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">Review History</span>
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{reviews.length} reviews</span>
            </div>
            {reviews.length === 0 ? (
              <p style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'center', padding: '20px 0' }}>No reviews yet.</p>
            ) : reviews.map(r => (
              <div key={r.review_id} style={{ padding: '10px 0', borderBottom: '1px solid var(--border-subtle)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, flexWrap: 'wrap' }}>
                  <span className={`badge ${r.verdict === 'approved' ? 'badge-green' : r.verdict === 'rejected' ? 'badge-red' : 'badge-amber'}`}>
                    {r.verdict.replace(/_/g, ' ')}
                  </span>
                  {r.reviewer_id && <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Reviewer #{r.reviewer_id}</span>}
                  <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                    {new Date(r.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
                    {', '}
                    {new Date(r.created_at).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
                {r.notes && <p style={{ fontSize: 12, color: 'var(--text-secondary)', margin: 0 }}>{r.notes}</p>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}


function ResolutionBadge({ r }) {
  const map = { resolved: 'badge-green', partially_resolved: 'badge-amber', unresolved: 'badge-red', pending: 'badge-amber', escalated: 'badge-purple', unknown: 'badge-gray' };
  return <span className={`badge ${map[r] || 'badge-gray'}`}>{r?.replace(/_/g, ' ')}</span>;
}
