import { useState, useEffect, useRef } from 'react';
import { api } from '../api';
import { Send, Plus, PhoneOff, Mic, ExternalLink, Trash2, Activity, CheckCircle, AlertTriangle, TrendingUp } from 'lucide-react';

let _idKey = 0;
const nextKey = () => `demo-${Date.now()}-${++_idKey}`;

const STORAGE_KEY = 'echoinsight_demo_session';

function loadSession() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null'); } catch { return null; }
}
function saveSession(data) { localStorage.setItem(STORAGE_KEY, JSON.stringify(data)); }
function clearSession() { localStorage.removeItem(STORAGE_KEY); }

const SENTIMENT_COLOR = {
  positive: 'var(--green)', neutral: 'var(--text-muted)',
  frustrated: 'var(--amber)', angry: 'var(--red)',
};

const COMMITMENT_STATUS_BADGE = {
  proposed: 'badge-amber', accepted: 'badge-blue', scheduled: 'badge-blue',
  completed: 'badge-green', cancelled: 'badge-gray', uncertain: 'badge-amber',
};

// D20: Provisional state panel displayed after each turn append
function ProvisionalStatePanel({ state, commitments }) {
  if (!state && (!commitments || commitments.length === 0)) {
    return (
      <div style={{ textAlign: 'center', padding: 32, color: 'var(--text-muted)' }}>
        <Activity size={24} style={{ marginBottom: 8, opacity: 0.4 }} />
        <p style={{ fontSize: 13 }}>Provisional state updates after each turn is appended.</p>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Live state */}
      {state && (
        <div>
          <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)', letterSpacing: '0.06em', marginBottom: 8 }}>
            Live State <span style={{ color: 'var(--amber)', fontStyle: 'italic', fontSize: 10, fontWeight: 400 }}>provisional</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {state.issue && (
              <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                <span style={{ fontSize: 10, color: 'var(--text-muted)', minWidth: 80, paddingTop: 2 }}>Issue</span>
                <span style={{ fontSize: 12 }}>{state.issue}</span>
              </div>
            )}
            {state.resolution && (
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <span style={{ fontSize: 10, color: 'var(--text-muted)', minWidth: 80 }}>Resolution</span>
                <span style={{ fontSize: 12, textTransform: 'capitalize' }}>{state.resolution?.replace(/_/g, ' ')}</span>
              </div>
            )}
            {state.customer_sentiment && (
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <span style={{ fontSize: 10, color: 'var(--text-muted)', minWidth: 80 }}>Sentiment</span>
                <span style={{
                  fontSize: 12, fontWeight: 600,
                  color: SENTIMENT_COLOR[state.customer_sentiment] || 'var(--text-muted)',
                }}>{state.customer_sentiment}</span>
              </div>
            )}
            {state.churn_risk && state.churn_risk !== 'low' && (
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <span style={{ fontSize: 10, color: 'var(--text-muted)', minWidth: 80 }}>Churn Risk</span>
                <span className={`badge ${state.churn_risk === 'high' ? 'badge-red' : 'badge-amber'}`}>{state.churn_risk}</span>
              </div>
            )}
            {state.unresolved_questions && state.unresolved_questions.length > 0 && (
              <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                <span style={{ fontSize: 10, color: 'var(--text-muted)', minWidth: 80, paddingTop: 2 }}>Open</span>
                <ul style={{ margin: 0, paddingLeft: 16, fontSize: 11, color: 'var(--amber)' }}>
                  {state.unresolved_questions.map((q, i) => <li key={i}>{q}</li>)}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Live commitment ledger */}
      {commitments && commitments.length > 0 && (
        <div>
          <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)', letterSpacing: '0.06em', marginBottom: 8 }}>
            Commitment Ledger ({commitments.length})
          </div>
          {commitments.map((c, i) => (
            <div key={i} style={{ padding: '8px 0', borderBottom: '1px solid var(--border-subtle)', display: 'flex', gap: 8, alignItems: 'flex-start' }}>
              <span className={`badge ${COMMITMENT_STATUS_BADGE[c.status] || 'badge-gray'}`} style={{ flexShrink: 0 }}>{c.status}</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 12 }}>{c.description}</div>
                {c.owner && <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Owner: {c.owner}</div>}
                {c.deadline && <div style={{ fontSize: 11, color: 'var(--amber)' }}>Due: {c.deadline}</div>}
              </div>
              {c.provisional && <span style={{ fontSize: 9, color: 'var(--amber)', fontStyle: 'italic' }}>provisional</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function LiveDemo() {
  const saved = loadSession();
  const [convId, setConvId] = useState(saved?.convId || null);
  const [turns, setTurns] = useState(saved?.turns || []);
  const [speaker, setSpeaker] = useState('agent');
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [ended, setEnded] = useState(saved?.ended || false);
  const [msg, setMsg] = useState(saved?.convId ? `Session restored: ${saved.convId.slice(0, 8)}` : '');
  const [jobId, setJobId] = useState(saved?.jobId || null);
  // D20: Track provisional state and ledger from last append response
  const [provisionalState, setProvisionalState] = useState(saved?.provisionalState || null);
  const [ledger, setLedger] = useState(saved?.ledger || []);
  const transcriptRef = useRef(null);

  useEffect(() => {
    if (convId) saveSession({ convId, turns, ended, jobId, provisionalState, ledger });
  }, [convId, turns, ended, jobId, provisionalState, ledger]);

  // Auto-scroll transcript
  useEffect(() => {
    if (transcriptRef.current) {
      transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight;
    }
  }, [turns]);

  const createConv = async () => {
    setLoading(true); setMsg('');
    try {
      const c = await api.createConversation('call');
      setConvId(c.id);
      setTurns([]);
      setEnded(false);
      setJobId(null);
      setProvisionalState(null);
      setLedger([]);
      setMsg(`Conversation started: ${c.id.slice(0, 8)}`);
    } catch (e) { setMsg(`Error: ${e.message}`); }
    finally { setLoading(false); }
  };

  const resetSession = () => {
    clearSession();
    setConvId(null); setTurns([]); setEnded(false); setJobId(null);
    setProvisionalState(null); setLedger([]);
    setMsg('Session cleared.');
  };

  const appendTurn = async (spk = speaker, t = text) => {
    if (!convId || !t.trim()) return;
    setLoading(true);
    try {
      const res = await api.appendTurn(convId, spk, t, nextKey());
      setTurns(prev => [...prev, { ...res, text_original: t }]);
      // D20: Update provisional state and ledger from response
      if (res.provisional_state) setProvisionalState(res.provisional_state);
      if (res.ledger) setLedger(res.ledger);
      if (spk === speaker) setText('');
    } catch (e) { setMsg(`Error: ${e.message}`); }
    finally { setLoading(false); }
  };

  const endConv = async () => {
    if (!convId) return;
    setLoading(true);
    try {
      const res = await api.endConversation(convId);
      setEnded(true);
      setJobId(res.job_id);
      setMsg(`Conversation ended. Analysis job queued: ${res.job_id?.slice(0, 8)}`);
    } catch (e) { setMsg(`Error: ${e.message}`); }
    finally { setLoading(false); }
  };

  const QUICK_TURNS = [
    { speaker: 'agent', text: 'Thank you for calling Union Mobile, my name is Alex. How can I help you today?' },
    { speaker: 'customer', text: 'Hi, I have no internet at home since yesterday morning. My account number is 12345678.' },
    { speaker: 'agent', text: 'I am sorry to hear that. Let me check your account right away.' },
    { speaker: 'agent', text: 'I can see there is an outage in your area. Our engineers will fix it by tomorrow 5pm.' },
    { speaker: 'customer', text: 'This is the third time this month! I am seriously thinking about switching providers.' },
    { speaker: 'agent', text: 'I completely understand your frustration. I will apply a credit to your account for the inconvenience.' },
    { speaker: 'customer', text: 'Okay, thank you. How much will the credit be?' },
    { speaker: 'agent', text: 'It will be ten dollars applied within 2 business days. Is there anything else I can help you with?' },
    { speaker: 'customer', text: 'No, that is all. Thank you.' },
    { speaker: 'agent', text: 'Thank you for calling Union Mobile. Have a great day.' },
  ];

  return (
    <div className="page">
      <div style={{ marginBottom: 16 }}>
        <h2 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>Live Console</h2>
        <p style={{ color: 'var(--text-muted)', fontSize: 13, marginTop: 4 }}>
          Create a conversation, append turns, and watch the provisional state and commitment ledger update in real time.
        </p>
      </div>

      {msg && (
        <div className="error-banner" style={{
          marginBottom: 12,
          background: msg.startsWith('Error') ? 'var(--red-bg)' : 'var(--green-bg)',
          borderColor: msg.startsWith('Error') ? 'var(--red)' : 'var(--green)',
          color: msg.startsWith('Error') ? 'var(--red)' : 'var(--green)',
        }}>{msg}</div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '340px 1fr 300px', gap: 14 }}>

        {/* Left: Controls */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* Session */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">Session</span>
              {convId && <button className="btn btn-ghost btn-sm" onClick={resetSession} style={{ color: 'var(--red)', fontSize: 11 }} title="Clear session"><Trash2 size={11} /> Clear</button>}
            </div>
            <button className="btn btn-primary" onClick={createConv} disabled={loading} style={{ marginBottom: 10, width: '100%' }}>
              <Plus size={14} /> {convId ? 'New Conversation' : 'Start Conversation'}
            </button>
            {convId && (
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 8, fontFamily: 'monospace', padding: '5px 8px', background: 'var(--bg-secondary)', borderRadius: 4, wordBreak: 'break-all' }}>
                ID: {convId}
                <span className={`badge ${ended ? 'badge-green' : 'badge-amber'}`} style={{ marginLeft: 8 }}>{ended ? 'ended' : 'active'}</span>
              </div>
            )}
            {convId && !ended && (
              <button className="btn btn-ghost" style={{ borderColor: 'var(--red)', color: 'var(--red)', marginBottom: 8, width: '100%' }} onClick={endConv} disabled={loading}>
                <PhoneOff size={14} /> End Conversation
              </button>
            )}
            {convId && (
              <button className="btn btn-ghost btn-sm" style={{ display: 'flex', alignItems: 'center', gap: 6, width: '100%' }}
                onClick={() => { window.location.hash = `#/conversation/${convId}`; }}>
                <ExternalLink size={12} /> View in Dashboard
              </button>
            )}
            {jobId && <div style={{ marginTop: 8, fontSize: 12, color: 'var(--amber)' }}>Analysis queued - check the conversation page in ~30s</div>}
          </div>

          {/* Quick Script - D20: show full text, not truncated */}
          <div className="card">
            <div className="card-header"><span className="card-title">Quick Script</span></div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5, maxHeight: 280, overflowY: 'auto' }}>
              {QUICK_TURNS.map((t, i) => (
                <button key={i} className="btn btn-ghost btn-sm"
                  style={{ justifyContent: 'flex-start', textAlign: 'left', fontSize: 11, whiteSpace: 'normal', height: 'auto', padding: '6px 8px' }}
                  onClick={() => appendTurn(t.speaker, t.text)} disabled={!convId || ended || loading}>
                  <span className={`badge ${t.speaker === 'agent' ? 'badge-blue' : 'badge-purple'}`} style={{ minWidth: 60, flexShrink: 0 }}>{t.speaker}</span>
                  <span style={{ marginLeft: 6 }}>{t.text}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Manual Turn */}
          {convId && !ended && (
            <div className="card">
              <div className="card-header"><span className="card-title">Custom Turn</span></div>
              <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
                {['agent', 'customer'].map(s => (
                  <button key={s} className={`btn ${speaker === s ? 'btn-primary' : 'btn-ghost'} btn-sm`} onClick={() => setSpeaker(s)} style={{ textTransform: 'capitalize', flex: 1 }}>{s}</button>
                ))}
              </div>
              <textarea className="input" value={text} onChange={e => setText(e.target.value)}
                placeholder="Enter turn text..." rows={3}
                style={{ width: '100%', resize: 'vertical', marginBottom: 8, boxSizing: 'border-box' }}
                onKeyDown={e => { if (e.key === 'Enter' && e.ctrlKey) appendTurn(); }} />
              <button className="btn btn-primary btn-sm" onClick={() => appendTurn()} disabled={!text.trim() || loading} style={{ width: '100%' }}>
                <Send size={13} /> Send Turn
              </button>
            </div>
          )}
        </div>

        {/* Middle: Transcript */}
        <div className="card" style={{ padding: 0, display: 'flex', flexDirection: 'column' }}>
          <div className="card-header" style={{ padding: '12px 16px' }}>
            <span className="card-title">Transcript</span>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{turns.length} turns</span>
          </div>
          <div ref={transcriptRef} style={{ flex: 1, overflowY: 'auto', padding: '12px 16px', maxHeight: 600 }}>
            {turns.length === 0 ? (
              <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>
                <Mic size={24} style={{ marginBottom: 8, opacity: 0.4 }} />
                <p style={{ fontSize: 13 }}>No turns yet. Start a conversation and add turns.</p>
              </div>
            ) : (
              <div className="transcript">
                {turns.map(t => (
                  <div key={t.turn_id} className={`turn turn-${t.speaker}`}>
                    <div className="turn-avatar" style={{ fontSize: 9 }}>{t.speaker === 'agent' ? 'AGT' : 'CST'}</div>
                    <div className="turn-body">
                      <div className="turn-meta">
                        <strong style={{ textTransform: 'capitalize' }}>{t.speaker}</strong>
                        <span>{t.turn_id}</span>
                        <span className={`badge ${t.extraction_status === 'completed' ? 'badge-green' : 'badge-gray'}`} style={{ fontSize: 9 }}>{t.extraction_status}</span>
                      </div>
                      <div className="turn-text">{t.text_redacted}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right: D20 Provisional State + Commitment Ledger */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Live State</span>
            {convId && !ended && (
              <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: 'var(--green)' }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--green)', display: 'inline-block', animation: 'pulse 2s infinite' }} />
                live
              </span>
            )}
          </div>
          <ProvisionalStatePanel state={provisionalState} commitments={ledger} />
        </div>
      </div>
    </div>
  );
}
