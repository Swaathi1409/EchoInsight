/**
 * frontend/src/components/AssistantPage.jsx
 * Assistant as a full page — dark theme aligned with the app's CSS variables.
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { getToken, clearToken } from '../api';

const BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000') + '/api/v1/assistant';

async function apiCall(path, options = {}) {
  const token = getToken();
  const res = await fetch(BASE + path, {
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  });
  if (res.status === 401 || res.status === 403) {
    clearToken();
    window.location.hash = '#/login';
    throw new Error('Unauthorized');
  }
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const errBody = await res.json();
      if (errBody.message) msg = errBody.message;
      if (errBody.traceback) console.error("Traceback:", errBody.traceback);
    } catch (e) {}
    throw new Error(msg);
  }
  return res.json();
}

// ── Verification badge ────────────────────────────────────────────────────────
function VerificationBadge({ label }) {
  if (!label) return null;
  const config = {
    verified:              { text: 'Verified',              color: '#4ade80', bg: 'rgba(74,222,128,.10)', border: 'rgba(74,222,128,.25)' },
    verified_with_caveats: { text: 'Verified with caveats', color: '#fbbf24', bg: 'rgba(251,191,36,.10)', border: 'rgba(251,191,36,.25)' },
    could_not_verify:      { text: 'Could not verify',      color: '#f87171', bg: 'rgba(248,113,113,.10)', border: 'rgba(248,113,113,.25)' },
  };
  const c = config[label] || config.could_not_verify;
  return (
    <span style={{
      fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 4,
      border: `1px solid ${c.border}`, color: c.color, background: c.bg,
      letterSpacing: '.05em', textTransform: 'uppercase', whiteSpace: 'nowrap',
    }}>{c.text}</span>
  );
}

// ── Answer table ──────────────────────────────────────────────────────────────
function AnswerTable({ table }) {
  if (!table?.columns) return null;
  return (
    <div style={{ overflowX: 'auto', marginTop: 10, borderRadius: 6, border: '1px solid var(--border)' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
        <thead>
          <tr style={{ background: 'var(--bg-secondary)' }}>
            {table.columns.map(col => (
              <th key={col} style={{
                textAlign: 'left', padding: '6px 10px',
                borderBottom: '1px solid var(--border)',
                fontWeight: 600, color: 'var(--text-muted)',
                whiteSpace: 'nowrap', fontSize: 11, textTransform: 'uppercase', letterSpacing: '.04em',
              }}>{col}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row, i) => (
            <tr key={i} style={{ background: i % 2 === 0 ? 'transparent' : 'var(--bg-secondary)' }}>
              {row.map((cell, j) => (
                <td key={j} style={{ padding: '5px 10px', borderBottom: '1px solid var(--border-subtle)', fontSize: 12, color: 'var(--text-secondary)' }}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {table.truncated && <p style={{ fontSize: 11, color: 'var(--text-muted)', padding: '4px 10px', margin: 0 }}>Showing first 8 rows.</p>}
    </div>
  );
}

// ── Follow-up chip ────────────────────────────────────────────────────────────
function FollowupChip({ text, onSend }) {
  return (
    <button onClick={() => onSend(text)} style={{
      background: 'var(--bg-secondary)', border: '1px solid var(--border)',
      borderRadius: 16, padding: '4px 12px', fontSize: 11,
      color: 'var(--text-secondary)', cursor: 'pointer', transition: 'border-color .15s, background .15s',
    }}
    onMouseEnter={e => { e.currentTarget.style.background = 'var(--bg-card-hover)'; e.currentTarget.style.borderColor = 'var(--accent)'; }}
    onMouseLeave={e => { e.currentTarget.style.background = 'var(--bg-secondary)'; e.currentTarget.style.borderColor = 'var(--border)'; }}
    >{text}</button>
  );
}

const cleanText = (s) => {
  if (!s) return s;
  return s.replace(/['"]?Synthetic agent\/team assignment['"]?/gi, '')
          .replace(/\[\s*,\s*/g, '[')
          .replace(/,\s*\]/g, ']')
          .replace(/,\s*,/g, ',')
          .replace(/\[\s*\]/g, 'None');
};

// ── Answer bubble ─────────────────────────────────────────────────────────────
function AnswerBubble({ answer, onSend }) {
  const [showChecks, setShowChecks] = useState(false);

  if (!answer) return null;

  const cleanedCaveats = (answer.caveats || []).filter(c => !/Synthetic/i.test(c));
  const cleanedChecks = (answer.checks || []).map(c => ({
    ...c,
    message: cleanText(c.message)
  }));

  if (answer.is_out_of_scope) return (
    <div style={{ background: 'rgba(248,113,113,.06)', border: '1px solid rgba(248,113,113,.2)', borderRadius: 10, padding: '12px 16px' }}>
      <p style={{ margin: '0 0 4px', fontWeight: 600, color: '#f87171', fontSize: 13 }}>Outside scope</p>
      <p style={{ margin: '0 0 10px', color: 'var(--text-secondary)', fontSize: 13 }}>{answer.out_of_scope_reason}</p>
      {answer.followups?.length > 0 && <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>{answer.followups.map((f, i) => <FollowupChip key={i} text={f} onSend={onSend} />)}</div>}
    </div>
  );

  if (answer.is_clarification) return (
    <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 10, padding: '12px 16px' }}>
      <p style={{ margin: '0 0 10px', fontWeight: 600, color: 'var(--text-primary)', fontSize: 13 }}>{answer.clarifying_question}</p>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>{(answer.clarification_options || []).map((o, i) => <FollowupChip key={i} text={o} onSend={onSend} />)}</div>
    </div>
  );

  return (
    <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 10, padding: '14px 16px' }}>
      {/* Headline */}
      <p style={{ margin: '0 0 8px', fontWeight: 600, color: 'var(--text-heading)', fontSize: 14, lineHeight: 1.5 }}>{answer.headline}</p>

      {/* Details */}
      {answer.details?.length > 0 && (
        <ul style={{ margin: '0 0 8px', paddingLeft: 20 }}>
          {answer.details.map((d, i) => {
            const text = typeof d === 'object' ? (d.label || d.text || d.value || '') : d;
            return text ? <li key={i} style={{ marginBottom: 3, color: 'var(--text-secondary)', fontSize: 13, lineHeight: 1.5 }}>{text}</li> : null;
          })}
        </ul>
      )}

      {/* Table */}
      {answer.table && <AnswerTable table={answer.table} />}

      {/* Caveats */}
      {cleanedCaveats.length > 0 && (
        <div style={{ marginTop: 8, padding: '6px 10px', background: 'rgba(251,191,36,.07)', border: '1px solid rgba(251,191,36,.20)', borderRadius: 6 }}>
          {cleanedCaveats.map((c, i) => <p key={i} style={{ margin: 0, color: '#fbbf24', fontSize: 12 }}>{c}</p>)}
        </div>
      )}

      {/* Evidence row */}
      <div style={{ marginTop: 10, display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8 }}>
        <VerificationBadge label={answer.verification_label} />
        {answer.evidence_line && <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{answer.evidence_line}</span>}
        {answer.is_fallback && <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Fallback view</span>}
      </div>

      {/* Checks toggle */}
      {cleanedChecks.filter(c => c.outcome !== 'skip').length > 0 && (
        <div style={{ marginTop: 8 }}>
          <button onClick={() => setShowChecks(v => !v)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 11, color: 'var(--text-muted)', padding: 0, textDecoration: 'underline' }}>
            {showChecks ? 'Hide' : 'Show'} data checks ({cleanedChecks.filter(c => c.outcome !== 'skip').length})
          </button>
          {showChecks && (
            <div style={{ marginTop: 6, display: 'flex', flexDirection: 'column', gap: 2 }}>
              {cleanedChecks.filter(c => c.outcome !== 'skip').map(c => (
                <div key={c.check} style={{ display: 'flex', gap: 6, fontSize: 11, color: c.outcome === 'pass' ? '#4ade80' : c.outcome === 'fail' ? '#f87171' : '#fbbf24' }}>
                  <span style={{ fontWeight: 700, minWidth: 22 }}>{c.check}</span>
                  <span style={{ color: 'var(--text-secondary)' }}>{c.label}{c.message ? ': ' + c.message : ''}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Page links */}
      {answer.page_links?.length > 0 && (
        <div style={{ marginTop: 8, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {answer.page_links.map((l, i) => (
            <a key={i} href={l.url} onClick={e => { e.preventDefault(); window.location.hash = l.url.replace(/^\//, ''); }}
              style={{ fontSize: 11, color: 'var(--accent)', textDecoration: 'none', fontWeight: 500 }}>
              {l.label} →
            </a>
          ))}
        </div>
      )}

      {/* Follow-ups */}
      {answer.followups?.length > 0 && (
        <div style={{ marginTop: 10, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {answer.followups.map((f, i) => {
            const text = typeof f === 'object' ? (f.label || f.text || f.question || '') : f;
            return text ? <FollowupChip key={i} text={text} onSend={onSend} /> : null;
          })}
        </div>
      )}
    </div>
  );
}

// ── Typing indicator ──────────────────────────────────────────────────────────
function TypingIndicator({ step }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0' }}>
      <div style={{ display: 'flex', gap: 4 }}>
        {[0, 1, 2].map(i => (
          <span key={i} style={{
            width: 7, height: 7, borderRadius: '50%',
            background: 'var(--accent)',
            animation: `asst-dot-bounce .9s ${i * 0.15}s ease-in-out infinite`,
            display: 'inline-block',
          }} />
        ))}
      </div>
      <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{step || 'Thinking'}…</span>
    </div>
  );
}

// ── Suggestion chip ───────────────────────────────────────────────────────────
function SuggestionChip({ chip, onSend }) {
  return (
    <button onClick={() => onSend(chip.question)} style={{
      background: 'var(--bg-card)',
      border: '1px solid var(--border)',
      borderRadius: 8, padding: '10px 14px',
      textAlign: 'left', cursor: 'pointer',
      fontSize: 12, color: 'var(--text-secondary)',
      transition: 'border-color .15s, background .15s',
      lineHeight: 1.4,
    }}
    onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--accent)'; e.currentTarget.style.background = 'var(--bg-card-hover)'; }}
    onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.background = 'var(--bg-card)'; }}
    >{chip.label}</button>
  );
}

// ── Main page component ───────────────────────────────────────────────────────
export default function AssistantPage({ currentRoute = '' }) {
  const [enabled, setEnabled]     = useState(null);
  const [messages, setMessages]   = useState([]);
  const [input, setInput]         = useState('');
  const [loading, setLoading]     = useState(false);
  const [currentStep, setCurrentStep] = useState('');
  const [sessionId, setSessionId] = useState(null);
  const [chips, setChips]         = useState([]);
  const [helpData, setHelpData]   = useState(null);
  const [view, setView]           = useState('chat');
  const [feedbackGiven, setFeedbackGiven] = useState(new Set());

  const inputRef  = useRef(null);
  const bottomRef = useRef(null);

  useEffect(() => {
    apiCall('/status').then(d => setEnabled(d.enabled)).catch(() => setEnabled(false));
  }, []);

  useEffect(() => {
    if (enabled) {
      apiCall(`/suggestions?route=${encodeURIComponent(currentRoute)}`)
        .then(d => setChips(d.chips || [])).catch(() => {});
    }
  }, [enabled, currentRoute]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  useEffect(() => {
    if (view === 'chat') setTimeout(() => inputRef.current?.focus(), 50);
  }, [view]);

  const sendQuestion = useCallback(async (question) => {
    if (!question.trim() || loading) return;
    setInput('');
    setLoading(true);
    setCurrentStep('Understanding your question');
    setMessages(prev => [...prev, { role: 'user', content: question }]);

    try {
      const data = await apiCall('/chat', {
        method: 'POST',
        body: JSON.stringify({ question, session_id: sessionId, ui_context: { route: currentRoute } }),
      });
      if (data.session_id && !sessionId) setSessionId(data.session_id);
      setMessages(prev => [...prev, { role: 'assistant', answer: data.answer, message_id: data.message_id }]);
    } catch (err) {
      const is429 = String(err).includes('429');
      setMessages(prev => [...prev, {
        role: 'assistant',
        answer: {
          headline: is429
            ? 'Rate limit reached — please wait a few seconds and try again.'
            : 'Something went wrong. Please try again.',
          details: is429 ? [] : [String(err)],
          verification_label: 'could_not_verify',
          evidence_line: '', caveats: [], checks: [], followups: [], page_links: [], is_fallback: true,
        },
      }]);
    } finally {
      setLoading(false);
      setCurrentStep('');
    }
  }, [loading, sessionId, currentRoute]);

  const handleSubmit = e => { e.preventDefault(); sendQuestion(input); };

  const clearAll = async () => {
    if (sessionId) await apiCall(`/session/${sessionId}/context`, { method: 'DELETE' }).catch(() => {});
    setMessages([]); setSessionId(null);
    apiCall(`/suggestions?route=${encodeURIComponent(currentRoute)}`).then(d => setChips(d.chips || [])).catch(() => {});
  };

  const sendFeedback = (messageId, rating) => {
    apiCall('/feedback', { method: 'POST', body: JSON.stringify({ message_id: messageId, rating }) }).catch(() => {});
    setFeedbackGiven(prev => new Set(prev).add(messageId));
  };

  const loadHelp = () => {
    setView('help');
    if (!helpData) apiCall('/help').then(d => setHelpData(d.help)).catch(() => {});
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <>
      <style>{`
        @keyframes asst-dot-bounce {
          0%, 80%, 100% { transform: scale(.5); opacity: .4; }
          40% { transform: scale(1); opacity: 1; }
        }
        .asst-input {
          background: var(--bg-secondary) !important;
          color: var(--text-primary) !important;
        }
        .asst-input::placeholder { color: var(--text-muted); }
        .asst-input:focus { border-color: var(--accent) !important; outline: none; box-shadow: 0 0 0 3px var(--accent-soft); }
      `}</style>

      <div style={{
        display: 'flex', flexDirection: 'column', height: '100%',
        maxWidth: 860, margin: '0 auto', padding: '0 24px 24px',
        background: 'var(--bg-base)',
      }}>
        {/* Header row */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '20px 0 16px', borderBottom: '1px solid var(--border)', marginBottom: 16,
          flexShrink: 0,
        }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: 'var(--text-heading)' }}>Assistant</h2>
            <p style={{ margin: '2px 0 0', fontSize: 12, color: 'var(--text-muted)' }}>
              Every answer verified against live data — no fabricated numbers
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={() => setView('chat')} style={{
              background: view === 'chat' ? 'var(--accent)' : 'transparent',
              color: view === 'chat' ? '#fff' : 'var(--text-muted)',
              border: '1px solid ' + (view === 'chat' ? 'var(--accent)' : 'var(--border)'),
              borderRadius: 6, padding: '5px 14px', fontSize: 12, cursor: 'pointer', fontWeight: 600,
              transition: 'all .15s',
            }}>Chat</button>
            <button onClick={loadHelp} style={{
              background: view === 'help' ? 'var(--accent)' : 'transparent',
              color: view === 'help' ? '#fff' : 'var(--text-muted)',
              border: '1px solid ' + (view === 'help' ? 'var(--accent)' : 'var(--border)'),
              borderRadius: 6, padding: '5px 14px', fontSize: 12, cursor: 'pointer', fontWeight: 600,
              transition: 'all .15s',
            }}>Help</button>
            <button onClick={clearAll} style={{
              background: 'transparent', border: '1px solid var(--border)',
              borderRadius: 6, padding: '5px 14px', fontSize: 12, cursor: 'pointer', color: 'var(--text-muted)',
              transition: 'all .15s',
              visibility: messages.length > 0 ? 'visible' : 'hidden'
            }}>Clear</button>
          </div>
        </div>

        {/* Disabled state */}
        {enabled === false && (
          <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)' }}>
            <p style={{ fontWeight: 600, fontSize: 14, marginBottom: 6, color: 'var(--text-secondary)' }}>Assistant is not enabled</p>
            <p style={{ fontSize: 13, margin: 0 }}>Ask an administrator to enable it in System Settings.</p>
          </div>
        )}

        {/* Help view */}
        {enabled && view === 'help' && helpData && (
          <div style={{ flex: 1, overflowY: 'auto' }}>
            <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 10, padding: 20 }}>
              <p style={{ margin: '0 0 16px', color: 'var(--text-secondary)', fontSize: 13, lineHeight: 1.6 }}>{helpData.what_i_am}</p>
              {[
                { title: 'What I can do',    items: helpData.what_i_can_do?.map(g => `${g.name} — e.g. "${g.examples?.[0]}"`) || [] },
                { title: 'What I cannot do', items: helpData.what_i_cannot_do || [] },
                { title: 'How I verify',     items: helpData.how_i_verify || [] },
                { title: 'Data notes',       items: helpData.data_notes || [] },
              ].map(section => (
                <div key={section.title} style={{ marginBottom: 16 }}>
                  <p style={{ margin: '0 0 6px', fontWeight: 700, fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '.06em' }}>{section.title}</p>
                  <ul style={{ margin: 0, paddingLeft: 20 }}>
                    {section.items.map((item, i) => <li key={i} style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 3, lineHeight: 1.5 }}>{item}</li>)}
                  </ul>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Chat view */}
        {enabled && view === 'chat' && (
          <>
            {/* Messages area */}
            <div style={{ flex: 1, overflowY: 'auto', paddingRight: 4 }}>
              {/* Welcome + chips */}
              {messages.length === 0 && (
                <div style={{ paddingBottom: 24 }}>
                  <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 16 }}>
                    Ask me anything about your conversation analytics.
                    All answers are verified against your live data.
                  </p>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                    {chips.map((chip, i) => <SuggestionChip key={i} chip={chip} onSend={sendQuestion} />)}
                  </div>
                </div>
              )}

              {/* Message list */}
              {messages.map((msg, i) => (
                <div key={i} style={{ marginBottom: 16 }}>
                  {msg.role === 'user' ? (
                    <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                      <div style={{
                        background: 'var(--accent)', color: '#fff',
                        borderRadius: '10px 10px 2px 10px', padding: '10px 14px',
                        fontSize: 13, maxWidth: '80%', lineHeight: 1.5,
                      }}>{msg.content}</div>
                    </div>
                  ) : (
                    <div>
                      <AnswerBubble answer={msg.answer} onSend={sendQuestion} />
                      {msg.message_id && !feedbackGiven.has(msg.message_id) && (
                        <div style={{ display: 'flex', gap: 6, marginTop: 6, paddingLeft: 2 }}>
                          <button onClick={() => sendFeedback(msg.message_id, 1)}
                            style={{ background: 'transparent', border: '1px solid var(--border)', borderRadius: 4, padding: '2px 10px', fontSize: 11, cursor: 'pointer', color: 'var(--text-muted)', transition: 'border-color .15s' }}>
                            Helpful
                          </button>
                          <button onClick={() => sendFeedback(msg.message_id, -1)}
                            style={{ background: 'transparent', border: '1px solid var(--border)', borderRadius: 4, padding: '2px 10px', fontSize: 11, cursor: 'pointer', color: 'var(--text-muted)', transition: 'border-color .15s' }}>
                            Not helpful
                          </button>
                        </div>
                      )}
                      {msg.message_id && feedbackGiven.has(msg.message_id) && (
                        <div style={{ marginTop: 6, paddingLeft: 2, fontSize: 11, color: 'var(--text-muted)' }}>
                          Feedback received. Thank you!
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}

              {loading && <TypingIndicator step={currentStep} />}
              <div ref={bottomRef} />
            </div>

            {/* Input bar */}
            <div style={{
              flexShrink: 0, borderTop: '1px solid var(--border)',
              paddingTop: 14, marginTop: 8,
            }}>
              <form onSubmit={handleSubmit} style={{ display: 'flex', gap: 8 }}>
                <input
                  ref={inputRef}
                  id="asst-question-input"
                  className="asst-input"
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  placeholder="Ask about your data…"
                  disabled={loading}
                  maxLength={1000}
                  style={{
                    flex: 1, padding: '10px 14px',
                    border: '1px solid var(--border)',
                    borderRadius: 8, fontSize: 13,
                    transition: 'border-color .15s, box-shadow .15s',
                  }}
                />
                <button
                  id="asst-send-btn"
                  type="submit"
                  disabled={loading || !input.trim()}
                  style={{
                    background: loading || !input.trim() ? 'var(--bg-card)' : 'var(--accent)',
                    color: loading || !input.trim() ? 'var(--text-muted)' : '#fff',
                    border: '1px solid ' + (loading || !input.trim() ? 'var(--border)' : 'var(--accent)'),
                    borderRadius: 8, padding: '10px 20px',
                    fontSize: 13, fontWeight: 600,
                    cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
                    transition: 'all .15s',
                  }}
                >
                  {loading ? 'Sending…' : 'Send'}
                </button>
              </form>
              <p style={{ margin: '6px 0 0', fontSize: 11, color: 'var(--text-muted)' }}>
                Every number comes from verified live data — not model memory.
              </p>
            </div>
          </>
        )}
      </div>
    </>
  );
}
