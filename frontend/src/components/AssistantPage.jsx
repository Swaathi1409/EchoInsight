/**
 * frontend/src/components/AssistantPage.jsx
 * Assistant as a full page — matches the existing app theme exactly.
 * No floating panel; lives in the main content area like other tabs.
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { getToken } from '../api';

const BASE = '/api/v1/assistant';

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
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// ── Verification badge ────────────────────────────────────────────────────────
function VerificationBadge({ label }) {
  const config = {
    verified:              { text: 'Verified',              color: 'var(--green)',  bg: 'rgba(22,163,74,.08)',   border: 'rgba(22,163,74,.25)' },
    verified_with_caveats: { text: 'Verified with caveats', color: 'var(--yellow, #b45309)', bg: 'rgba(180,83,9,.08)',   border: 'rgba(180,83,9,.25)' },
    could_not_verify:      { text: 'Could not verify',      color: 'var(--red)',    bg: 'rgba(185,28,28,.08)',   border: 'rgba(185,28,28,.25)' },
  };
  const c = config[label] || config.could_not_verify;
  return (
    <span style={{
      fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 4,
      border: `1px solid ${c.border}`, color: c.color, background: c.bg,
      letterSpacing: '.02em', textTransform: 'uppercase',
    }}>{c.text}</span>
  );
}

// ── Answer table ─────────────────────────────────────────────────────────────
function AnswerTable({ table }) {
  if (!table?.columns) return null;
  return (
    <div style={{ overflowX: 'auto', marginTop: 10, borderRadius: 6, border: '1px solid var(--border)' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
        <thead>
          <tr style={{ background: 'var(--surface, #f8fafc)' }}>
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
            <tr key={i} style={{ background: i % 2 === 0 ? 'transparent' : 'var(--surface, #f8fafc)' }}>
              {row.map((cell, j) => (
                <td key={j} style={{ padding: '5px 10px', borderBottom: '1px solid var(--border)', fontSize: 12, color: 'var(--text)' }}>{cell}</td>
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
      background: 'var(--card-bg, #fff)', border: '1px solid var(--border)',
      borderRadius: 16, padding: '4px 12px', fontSize: 11,
      color: 'var(--text)', cursor: 'pointer', transition: 'background .15s',
    }}
    onMouseEnter={e => e.currentTarget.style.background = 'var(--hover-bg, #f1f5f9)'}
    onMouseLeave={e => e.currentTarget.style.background = 'var(--card-bg, #fff)'}
    >{text}</button>
  );
}

// ── Answer bubble ─────────────────────────────────────────────────────────────
function AnswerBubble({ answer, onSend }) {
  const [showChecks, setShowChecks] = useState(false);

  if (answer.is_out_of_scope) return (
    <div style={{ background: 'rgba(185,28,28,.06)', border: '1px solid rgba(185,28,28,.2)', borderRadius: 10, padding: '12px 16px' }}>
      <p style={{ margin: '0 0 4px', fontWeight: 600, color: 'var(--red, #b91c1c)', fontSize: 13 }}>Outside scope</p>
      <p style={{ margin: '0 0 10px', color: 'var(--text)', fontSize: 13 }}>{answer.out_of_scope_reason}</p>
      {answer.followups?.length > 0 && <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>{answer.followups.map((f, i) => <FollowupChip key={i} text={f} onSend={onSend} />)}</div>}
    </div>
  );

  if (answer.is_clarification) return (
    <div style={{ background: 'var(--card-bg, #fff)', border: '1px solid var(--border)', borderRadius: 10, padding: '12px 16px' }}>
      <p style={{ margin: '0 0 10px', fontWeight: 600, color: 'var(--text)', fontSize: 13 }}>{answer.clarifying_question}</p>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>{(answer.clarification_options || []).map((o, i) => <FollowupChip key={i} text={o} onSend={onSend} />)}</div>
    </div>
  );

  return (
    <div style={{ background: 'var(--card-bg, #fff)', border: '1px solid var(--border)', borderRadius: 10, padding: '12px 16px' }}>
      {/* Headline */}
      <p style={{ margin: '0 0 8px', fontWeight: 600, color: 'var(--text)', fontSize: 14, lineHeight: 1.5 }}>{answer.headline}</p>

      {/* Details */}
      {answer.details?.length > 0 && (
        <ul style={{ margin: '0 0 8px', paddingLeft: 20 }}>
          {answer.details.map((d, i) => <li key={i} style={{ marginBottom: 3, color: 'var(--text)', fontSize: 13, lineHeight: 1.5 }}>{d}</li>)}
        </ul>
      )}

      {/* Table */}
      <AnswerTable table={answer.table} />

      {/* Caveats */}
      {answer.caveats?.length > 0 && (
        <div style={{ marginTop: 8, padding: '6px 10px', background: 'rgba(180,83,9,.06)', border: '1px solid rgba(180,83,9,.2)', borderRadius: 6 }}>
          {answer.caveats.map((c, i) => <p key={i} style={{ margin: 0, color: 'var(--yellow, #92400e)', fontSize: 12 }}>{c}</p>)}
        </div>
      )}

      {/* Evidence row */}
      <div style={{ marginTop: 10, display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8 }}>
        <VerificationBadge label={answer.verification_label} />
        {answer.evidence_line && <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{answer.evidence_line}</span>}
        {answer.is_fallback && <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Fallback view</span>}
      </div>

      {/* Checks toggle */}
      {answer.checks?.filter(c => c.outcome !== 'skip').length > 0 && (
        <div style={{ marginTop: 8 }}>
          <button onClick={() => setShowChecks(v => !v)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 11, color: 'var(--text-muted)', padding: 0, textDecoration: 'underline' }}>
            {showChecks ? 'Hide' : 'Show'} data checks ({answer.checks.filter(c => c.outcome !== 'skip').length})
          </button>
          {showChecks && (
            <div style={{ marginTop: 6, display: 'flex', flexDirection: 'column', gap: 2 }}>
              {answer.checks.filter(c => c.outcome !== 'skip').map(c => (
                <div key={c.check} style={{ display: 'flex', gap: 6, fontSize: 11, color: c.outcome === 'pass' ? 'var(--green, #16a34a)' : c.outcome === 'fail' ? 'var(--red, #b91c1c)' : 'var(--yellow, #b45309)' }}>
                  <span style={{ fontWeight: 700, minWidth: 22 }}>{c.check}</span>
                  <span>{c.label}{c.message ? ': ' + c.message : ''}</span>
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
              style={{ fontSize: 11, color: 'var(--primary, #2563eb)', textDecoration: 'none', fontWeight: 500 }}>
              {l.label} →
            </a>
          ))}
        </div>
      )}

      {/* Follow-ups */}
      {answer.followups?.length > 0 && (
        <div style={{ marginTop: 10, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {answer.followups.map((f, i) => <FollowupChip key={i} text={f} onSend={onSend} />)}
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
            background: 'var(--primary, #2563eb)',
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
      background: 'var(--card-bg, #fff)',
      border: '1px solid var(--border)',
      borderRadius: 8, padding: '10px 14px',
      textAlign: 'left', cursor: 'pointer',
      fontSize: 12, color: 'var(--text)',
      transition: 'border-color .15s, background .15s',
      lineHeight: 1.4,
    }}
    onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--primary, #2563eb)'; e.currentTarget.style.background = 'rgba(37,99,235,.04)'; }}
    onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.background = 'var(--card-bg, #fff)'; }}
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
  const [view, setView]           = useState('chat'); // 'chat' | 'help'

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
      setMessages(prev => [...prev, {
        role: 'assistant',
        answer: {
          headline: 'Something went wrong. Please try again.',
          details: [String(err)],
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

  const sendFeedback = (messageId, rating) =>
    apiCall('/feedback', { method: 'POST', body: JSON.stringify({ message_id: messageId, rating }) }).catch(() => {});

  const loadHelp = () => {
    setView('help');
    if (!helpData) apiCall('/help').then(d => setHelpData(d.help)).catch(() => {});
  };

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <>
      <style>{`
        @keyframes asst-dot-bounce {
          0%, 80%, 100% { transform: scale(.5); opacity: .4; }
          40% { transform: scale(1); opacity: 1; }
        }
        .asst-input:focus { border-color: var(--primary, #2563eb) !important; outline: none; }
      `}</style>

      <div style={{
        display: 'flex', flexDirection: 'column', height: '100%',
        maxWidth: 860, margin: '0 auto', padding: '0 24px 24px',
      }}>
        {/* Header row */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '20px 0 16px', borderBottom: '1px solid var(--border)', marginBottom: 16,
          flexShrink: 0,
        }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: 'var(--text)' }}>Assistant</h2>
            <p style={{ margin: '2px 0 0', fontSize: 12, color: 'var(--text-muted)' }}>
              Every answer verified against live data — no fabricated numbers
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={() => setView('chat')} style={{
              background: view === 'chat' ? 'var(--primary, #2563eb)' : 'var(--card-bg, #fff)',
              color: view === 'chat' ? '#fff' : 'var(--text-muted)',
              border: '1px solid ' + (view === 'chat' ? 'transparent' : 'var(--border)'),
              borderRadius: 6, padding: '5px 14px', fontSize: 12, cursor: 'pointer', fontWeight: 600,
            }}>Chat</button>
            <button onClick={loadHelp} style={{
              background: view === 'help' ? 'var(--primary, #2563eb)' : 'var(--card-bg, #fff)',
              color: view === 'help' ? '#fff' : 'var(--text-muted)',
              border: '1px solid ' + (view === 'help' ? 'transparent' : 'var(--border)'),
              borderRadius: 6, padding: '5px 14px', fontSize: 12, cursor: 'pointer', fontWeight: 600,
            }}>Help</button>
            {messages.length > 0 && (
              <button onClick={clearAll} style={{
                background: 'var(--card-bg, #fff)', border: '1px solid var(--border)',
                borderRadius: 6, padding: '5px 14px', fontSize: 12, cursor: 'pointer', color: 'var(--text-muted)',
              }}>Clear</button>
            )}
          </div>
        </div>

        {/* Disabled state */}
        {enabled === false && (
          <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)' }}>
            <p style={{ fontWeight: 600, fontSize: 14, marginBottom: 6 }}>Assistant is not enabled</p>
            <p style={{ fontSize: 13, margin: 0 }}>Ask an administrator to enable it in System Settings.</p>
          </div>
        )}

        {/* Help view */}
        {enabled && view === 'help' && helpData && (
          <div style={{ flex: 1, overflowY: 'auto' }}>
            <div className="card" style={{ padding: 20 }}>
              <p style={{ margin: '0 0 16px', color: 'var(--text)', fontSize: 13, lineHeight: 1.6 }}>{helpData.what_i_am}</p>
              {[
                { title: 'What I can do',    items: helpData.what_i_can_do?.map(g => `${g.name} — e.g. "${g.examples?.[0]}"`) || [] },
                { title: 'What I cannot do', items: helpData.what_i_cannot_do || [] },
                { title: 'How I verify',     items: helpData.how_i_verify || [] },
                { title: 'Data notes',       items: helpData.data_notes || [] },
              ].map(section => (
                <div key={section.title} style={{ marginBottom: 16 }}>
                  <p style={{ margin: '0 0 6px', fontWeight: 700, fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '.06em' }}>{section.title}</p>
                  <ul style={{ margin: 0, paddingLeft: 20 }}>
                    {section.items.map((item, i) => <li key={i} style={{ fontSize: 13, color: 'var(--text)', marginBottom: 3, lineHeight: 1.5 }}>{item}</li>)}
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
                        background: 'var(--primary, #2563eb)', color: '#fff',
                        borderRadius: 10, padding: '10px 14px',
                        fontSize: 13, maxWidth: '80%', lineHeight: 1.5,
                      }}>{msg.content}</div>
                    </div>
                  ) : (
                    <div>
                      <AnswerBubble answer={msg.answer} onSend={sendQuestion} />
                      {msg.message_id && (
                        <div style={{ display: 'flex', gap: 6, marginTop: 6, paddingLeft: 2 }}>
                          <button onClick={() => sendFeedback(msg.message_id, 1)}
                            style={{ background: 'none', border: '1px solid var(--border)', borderRadius: 4, padding: '2px 10px', fontSize: 11, cursor: 'pointer', color: 'var(--text-muted)' }}>
                            Helpful
                          </button>
                          <button onClick={() => sendFeedback(msg.message_id, -1)}
                            style={{ background: 'none', border: '1px solid var(--border)', borderRadius: 4, padding: '2px 10px', fontSize: 11, cursor: 'pointer', color: 'var(--text-muted)' }}>
                            Not helpful
                          </button>
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
                    background: 'var(--card-bg, #fff)',
                    color: 'var(--text)',
                    transition: 'border-color .15s',
                  }}
                />
                <button
                  id="asst-send-btn"
                  type="submit"
                  disabled={loading || !input.trim()}
                  style={{
                    background: loading || !input.trim() ? 'var(--surface, #e5e7eb)' : 'var(--primary, #2563eb)',
                    color: loading || !input.trim() ? 'var(--text-muted)' : '#fff',
                    border: 'none', borderRadius: 8, padding: '10px 20px',
                    fontSize: 13, fontWeight: 600, cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
                    transition: 'background .15s',
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
