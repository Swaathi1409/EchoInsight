/**
 * LiveAppendPanel: interactive panel for active conversations.
 * Shows the provisional state and commitment ledger, updating after each turn.
 * Used inside ConversationDetail for active conversations.
 */
import { useState, useRef, useEffect } from 'react';
import { api } from '../api';
import { Send, AlertCircle, CheckCircle, Clock, XCircle, AlertTriangle } from 'lucide-react';

const SPEAKERS = ['agent', 'customer'];

function CommitmentBadge({ status }) {
  const map = {
    proposed: 'badge-amber',
    accepted: 'badge-blue',
    scheduled: 'badge-blue',
    completed: 'badge-green',
    cancelled: 'badge-gray',
    uncertain: 'badge-amber',
  };
  return <span className={`badge ${map[status] || 'badge-gray'}`}>{status}</span>;
}

function SentimentBadge({ s }) {
  const colors = {
    positive: 'var(--green)',
    neutral: 'var(--text-muted)',
    frustrated: 'var(--amber)',
    angry: 'var(--red)',
  };
  return (
    <span style={{ fontSize: 12, color: colors[s] || 'var(--text-muted)', fontWeight: 600 }}>
      {s || 'neutral'}
    </span>
  );
}

function ProvState({ state }) {
  if (!state) return null;
  const openCommits = (state.commitments || []).filter(c => !['completed', 'cancelled'].includes(c.status));
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* State chips */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        <div style={{ background: 'var(--bg-secondary)', borderRadius: 6, padding: '4px 10px', fontSize: 12 }}>
          <span style={{ color: 'var(--text-muted)', marginRight: 4 }}>Resolution:</span>
          <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{state.resolution || 'unknown'}</span>
        </div>
        <div style={{ background: 'var(--bg-secondary)', borderRadius: 6, padding: '4px 10px', fontSize: 12 }}>
          <span style={{ color: 'var(--text-muted)', marginRight: 4 }}>Sentiment:</span>
          <SentimentBadge s={state.sentiment_current} />
        </div>
        <div style={{ background: 'var(--bg-secondary)', borderRadius: 6, padding: '4px 10px', fontSize: 12 }}>
          <span style={{ color: 'var(--text-muted)', marginRight: 4 }}>Churn:</span>
          <span style={{ fontWeight: 600 }}>{state.churn_risk || 'low'}</span>
        </div>
      </div>

      {/* Commitment ledger */}
      {(state.commitments || []).length > 0 && (
        <div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Commitment Ledger — {openCommits.length} open
          </div>
          {state.commitments.map((c, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '6px 0', borderBottom: '1px solid var(--border-subtle)' }}>
              <CommitmentBadge status={c.status} />
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 12, color: 'var(--text-primary)' }}>{c.description}</div>
                {c.owner && <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Owner: {c.owner}</div>}
                {c.deadline && <div style={{ fontSize: 11, color: 'var(--amber)' }}>Due: {c.deadline} {c.deadline_flag && `(${c.deadline_flag})`}</div>}
              </div>
              {c.provisional && (
                <span className="badge badge-amber" style={{ fontSize: 10 }}>provisional</span>
              )}
            </div>
          ))}
        </div>
      )}

      {(state.commitments || []).length === 0 && (
        <div style={{ fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic' }}>No commitments detected yet.</div>
      )}
    </div>
  );
}

export default function LiveAppendPanel({ conv, onTurnAdded }) {
  const [speaker, setSpeaker] = useState('agent');
  const [text, setText] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [lastState, setLastState] = useState(conv?.provisional_state || null);
  const [turns, setTurns] = useState([]);
  const textRef = useRef(null);
  const keyCounter = useRef(0);

  useEffect(() => {
    if (conv?.provisional_state) {
      setLastState(conv.provisional_state);
    }
  }, [conv?.provisional_state]);

  const sendTurn = async () => {
    const trimmed = text.trim();
    if (!trimmed || sending) return;
    setSending(true);
    setError('');
    try {
      keyCounter.current += 1;
      const ikey = `live-${conv.id}-${keyCounter.current}-${Date.now()}`;
      const resp = await api.appendTurn(conv.id, speaker, trimmed, ikey);

      // Update local turn list
      const newTurn = { turn_id: resp.turn_id, speaker, text_redacted: trimmed, timestamp: new Date().toISOString() };
      setTurns(prev => [...prev, newTurn]);

      // Update provisional state from response
      if (resp.provisional_state) setLastState(resp.provisional_state);

      setText('');
      textRef.current?.focus();
      onTurnAdded && onTurnAdded(resp);
    } catch (e) {
      setError(e.message || 'Failed to send turn');
    } finally {
      setSending(false);
    }
  };

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendTurn(); }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Turn input */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">Append Turn</span>
          <span className="badge badge-amber" style={{ fontSize: 10 }}>Live — Provisional</span>
        </div>
        <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
          {SPEAKERS.map(s => (
            <button key={s} onClick={() => setSpeaker(s)}
              className={`btn btn-sm ${speaker === s ? 'btn-primary' : 'btn-ghost'}`}
              style={{ textTransform: 'capitalize' }}>
              {s}
            </button>
          ))}
        </div>
        <textarea
          ref={textRef}
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={handleKey}
          placeholder={`Type ${speaker} turn… (Enter to send)`}
          rows={3}
          style={{
            width: '100%', boxSizing: 'border-box', background: 'var(--bg-secondary)',
            border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '8px 10px',
            color: 'var(--text-primary)', fontSize: 13, resize: 'vertical', outline: 'none',
            fontFamily: 'inherit',
          }}
        />
        {error && <div className="error-banner" style={{ marginTop: 6, fontSize: 12 }}>{error}</div>}
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 8 }}>
          <button className="btn btn-primary btn-sm" onClick={sendTurn} disabled={sending || !text.trim()}
            style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Send size={13} />
            {sending ? 'Sending…' : 'Send Turn'}
          </button>
        </div>
      </div>

      {/* Appended turns this session */}
      {turns.length > 0 && (
        <div className="card" style={{ maxHeight: 200, overflowY: 'auto' }}>
          <div className="card-header"><span className="card-title" style={{ fontSize: 12 }}>Session Turns</span></div>
          <div className="transcript">
            {turns.map(t => (
              <div key={t.turn_id} className={`turn turn-${t.speaker}`}>
                <div className="turn-body">
                  <div className="turn-meta">
                    <strong style={{ textTransform: 'capitalize' }}>{t.speaker}</strong>
                    <span>{t.turn_id}</span>
                  </div>
                  <div className="turn-text">{t.text_redacted}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Provisional state panel */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">Provisional State</span>
          <span className="badge badge-amber" style={{ fontSize: 10 }}>provisional — updates per turn</span>
        </div>
        {lastState
          ? <ProvState state={lastState} />
          : <p style={{ fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic' }}>
              Send turns to see the provisional state update in real time.
            </p>
        }
      </div>
    </div>
  );
}
