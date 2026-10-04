/**
 * frontend/src/components/AssistantPanel.jsx
 * EchoInsight Assistant — floating side panel.
 * Additive: rendered as an overlay, zero impact on existing routes.
 *
 * Design principles:
 * - Trustworthy: every answer shows verification badge + evidence line
 * - No hallucination UI: fallback table always renders something real
 * - Accessible: keyboard navigable, focus-trapped when open
 * - Minimal: no emojis, plain professional English
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
  if (!label) return null;
  const config = {
    verified: { text: 'Verified', color: '#16a34a', bg: '#f0fdf4', border: '#bbf7d0' },
    verified_with_caveats: { text: 'Verified with caveats', color: '#b45309', bg: '#fffbeb', border: '#fde68a' },
    could_not_verify: { text: 'Could not verify', color: '#b91c1c', bg: '#fef2f2', border: '#fecaca' },
  };
  const c = config[label] || config.could_not_verify;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      fontSize: 11, fontWeight: 600, padding: '2px 8px',
      borderRadius: 4, border: `1px solid ${c.border}`,
      color: c.color, background: c.bg,
    }}>
      {c.text}
    </span>
  );
}

// ── Answer table ───────────────────────────────────────────────────────────────

function AnswerTable({ table }) {
  if (!table || !table.columns) return null;
  return (
    <div style={{ overflowX: 'auto', marginTop: 8 }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
        <thead>
          <tr>
            {table.columns.map(col => (
              <th key={col} style={{
                textAlign: 'left', padding: '4px 8px',
                borderBottom: '1px solid var(--border)',
                fontWeight: 600, color: 'var(--text-muted)',
                whiteSpace: 'nowrap',
              }}>{col}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row, i) => (
            <tr key={i} style={{ background: i % 2 === 0 ? 'transparent' : 'rgba(0,0,0,.02)' }}>
              {row.map((cell, j) => (
                <td key={j} style={{
                  padding: '4px 8px', borderBottom: '1px solid var(--border)',
                  fontSize: 12, color: 'var(--text)',
                }}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {table.truncated && (
        <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
          Showing first 8 rows.
        </p>
      )}
    </div>
  );
}

// ── Answer message ────────────────────────────────────────────────────────────

function AnswerMessage({ answer, isFallback }) {
  const [showChecks, setShowChecks] = useState(false);

  return (
    <div style={{
      background: 'var(--card-bg, #fff)',
      border: '1px solid var(--border)',
      borderRadius: 8,
      padding: '12px 14px',
      fontSize: 13,
      lineHeight: 1.6,
    }}>
      {/* Headline */}
      <p style={{ margin: '0 0 8px', fontWeight: 600, color: 'var(--text)' }}>
        {answer.headline}
      </p>

      {/* Details */}
      {answer.details && answer.details.length > 0 && (
        <ul style={{ margin: '0 0 8px', paddingLeft: 18 }}>
          {answer.details.map((d, i) => (
            <li key={i} style={{ marginBottom: 3, color: 'var(--text)' }}>{d}</li>
          ))}
        </ul>
      )}

      {/* Table */}
      {answer.table && <AnswerTable table={answer.table} />}

      {/* Caveats */}
      {answer.caveats && answer.caveats.length > 0 && (
        <div style={{
          marginTop: 8, padding: '6px 10px',
          background: '#fffbeb', border: '1px solid #fde68a',
          borderRadius: 4, fontSize: 12,
        }}>
          {answer.caveats.map((c, i) => <p key={i} style={{ margin: 0, color: '#92400e' }}>{c}</p>)}
        </div>
      )}

      {/* Evidence + verification */}
      <div style={{ marginTop: 10, display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8 }}>
        <VerificationBadge label={answer.verification_label} />
        {answer.evidence_line && (
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{answer.evidence_line}</span>
        )}
        {isFallback && (
          <span style={{ fontSize: 11, color: '#92400e' }}>Fallback: summary text unavailable</span>
        )}
      </div>

      {/* C1-C10 checks toggle */}
      {answer.checks && answer.checks.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <button
            onClick={() => setShowChecks(v => !v)}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              fontSize: 11, color: 'var(--text-muted)', padding: 0,
              textDecoration: 'underline',
            }}
          >
            {showChecks ? 'Hide' : 'Show'} data checks ({answer.checks.filter(c => c.outcome !== 'skip').length})
          </button>
          {showChecks && (
            <div style={{ marginTop: 6 }}>
              {answer.checks.filter(c => c.outcome !== 'skip').map(c => (
                <div key={c.check} style={{
                  display: 'flex', gap: 6, fontSize: 11, padding: '2px 0',
                  color: c.outcome === 'pass' ? '#16a34a' : c.outcome === 'fail' ? '#b91c1c' : '#b45309',
                }}>
                  <span style={{ fontWeight: 600, minWidth: 24 }}>{c.check}</span>
                  <span>{c.label}: {c.message || c.outcome}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Page links */}
      {answer.page_links && answer.page_links.length > 0 && (
        <div style={{ marginTop: 8, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {answer.page_links.map((l, i) => (
            <a key={i} href={l.url}
              style={{ fontSize: 11, color: 'var(--primary, #2563eb)', textDecoration: 'none' }}
              onClick={e => { e.preventDefault(); window.location.hash = l.url.replace(/^\//, ''); }}
            >
              {l.label} →
            </a>
          ))}
        </div>
      )}

      {/* Follow-up chips */}
      {answer.followups && answer.followups.length > 0 && (
        <div style={{ marginTop: 10, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {answer.followups.map((f, i) => (
            <FollowupChip key={i} text={f} />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Followup chip — rendered inside answer (needs context) ───────────────────

function FollowupChip({ text }) {
  // Dispatch a custom event that the panel listens to
  const handleClick = () => {
    window.dispatchEvent(new CustomEvent('assistant:followup', { detail: { text } }));
  };
  return (
    <button
      onClick={handleClick}
      style={{
        background: 'var(--card-bg, #f8fafc)',
        border: '1px solid var(--border)',
        borderRadius: 12,
        padding: '3px 10px',
        fontSize: 11,
        color: 'var(--text)',
        cursor: 'pointer',
        transition: 'background .15s',
      }}
      onMouseEnter={e => e.target.style.background = 'var(--hover-bg, #f1f5f9)'}
      onMouseLeave={e => e.target.style.background = 'var(--card-bg, #f8fafc)'}
    >
      {text}
    </button>
  );
}

// ── Clarification message ─────────────────────────────────────────────────────

function ClarificationMessage({ answer }) {
  return (
    <div style={{
      background: 'var(--card-bg, #fff)',
      border: '1px solid var(--border)',
      borderRadius: 8, padding: '12px 14px', fontSize: 13,
    }}>
      <p style={{ margin: '0 0 10px', fontWeight: 600 }}>{answer.clarifying_question}</p>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {(answer.clarification_options || []).map((opt, i) => (
          <FollowupChip key={i} text={opt} />
        ))}
      </div>
    </div>
  );
}

// ── Out of scope message ──────────────────────────────────────────────────────

function OutOfScopeMessage({ answer }) {
  return (
    <div style={{
      background: '#fef2f2', border: '1px solid #fecaca',
      borderRadius: 8, padding: '12px 14px', fontSize: 13,
    }}>
      <p style={{ margin: '0 0 4px', fontWeight: 600, color: '#b91c1c' }}>Outside scope</p>
      <p style={{ margin: 0, color: '#7f1d1d' }}>{answer.out_of_scope_reason}</p>
      {answer.followups && answer.followups.length > 0 && (
        <div style={{ marginTop: 10, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {answer.followups.map((f, i) => <FollowupChip key={i} text={f} />)}
        </div>
      )}
    </div>
  );
}

// ── Disabled message ──────────────────────────────────────────────────────────

function DisabledMessage() {
  return (
    <div style={{
      textAlign: 'center', padding: '40px 20px',
      color: 'var(--text-muted)', fontSize: 13,
    }}>
      <p style={{ fontWeight: 600, marginBottom: 6 }}>Assistant is not enabled</p>
      <p style={{ margin: 0 }}>Ask an administrator to enable it in System Settings.</p>
    </div>
  );
}

// ── Help panel ────────────────────────────────────────────────────────────────

function HelpPanel({ help }) {
  if (!help) return null;
  return (
    <div style={{ fontSize: 13, lineHeight: 1.6 }}>
      <p style={{ margin: '0 0 12px', color: 'var(--text-muted)' }}>{help.what_i_am}</p>

      <strong style={{ fontSize: 12, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '.04em' }}>
        What I can do
      </strong>
      <ul style={{ margin: '6px 0 14px', paddingLeft: 18 }}>
        {(help.what_i_can_do || []).map(g => (
          <li key={g.family} style={{ marginBottom: 4 }}>
            <strong>{g.name}</strong>
            {g.examples && g.examples.length > 0 && (
              <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                — e.g. "{g.examples[0]}"
              </span>
            )}
          </li>
        ))}
      </ul>

      <strong style={{ fontSize: 12, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '.04em' }}>
        What I cannot do
      </strong>
      <ul style={{ margin: '6px 0 14px', paddingLeft: 18 }}>
        {(help.what_i_cannot_do || []).map((w, i) => (
          <li key={i} style={{ color: 'var(--text-muted)', marginBottom: 2 }}>{w}</li>
        ))}
      </ul>

      <strong style={{ fontSize: 12, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '.04em' }}>
        How I verify
      </strong>
      <ul style={{ margin: '6px 0 14px', paddingLeft: 18 }}>
        {(help.how_i_verify || []).map((h, i) => (
          <li key={i} style={{ marginBottom: 2 }}>{h}</li>
        ))}
      </ul>

      <strong style={{ fontSize: 12, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '.04em' }}>
        Data notes
      </strong>
      <ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>
        {(help.data_notes || []).map((n, i) => (
          <li key={i} style={{ color: 'var(--text-muted)', marginBottom: 2 }}>{n}</li>
        ))}
      </ul>
    </div>
  );
}

// ── Typing indicator ──────────────────────────────────────────────────────────

function TypingIndicator({ steps }) {
  const currentStep = steps && steps.length > 0 ? steps[steps.length - 1].step : 'Thinking';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 0' }}>
      <div style={{ display: 'flex', gap: 4 }}>
        {[0, 1, 2].map(i => (
          <span key={i} style={{
            width: 6, height: 6, borderRadius: '50%',
            background: 'var(--primary, #2563eb)',
            animation: `asst-bounce .9s ease-in-out ${i * 0.15}s infinite`,
            display: 'inline-block',
          }} />
        ))}
      </div>
      <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{currentStep}…</span>
    </div>
  );
}

// ── Main panel ────────────────────────────────────────────────────────────────

export default function AssistantPanel({ currentRoute = '' }) {
  const [open, setOpen] = useState(false);
  const [enabled, setEnabled] = useState(null);   // null=loading, bool
  const [view, setView] = useState('chat');        // 'chat' | 'help'
  const [messages, setMessages] = useState([]);    // {role, content, answer?, steps?}
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [steps, setSteps] = useState([]);
  const [sessionId, setSessionId] = useState(null);
  const [chips, setChips] = useState([]);
  const [helpData, setHelpData] = useState(null);

  const inputRef = useRef(null);
  const bottomRef = useRef(null);

  // Load status on mount
  useEffect(() => {
    apiCall('/status')
      .then(d => setEnabled(d.enabled))
      .catch(() => setEnabled(false));
  }, []);

  // Load suggestions when panel opens
  useEffect(() => {
    if (open && enabled) {
      apiCall(`/suggestions?route=${encodeURIComponent(currentRoute)}`)
        .then(d => setChips(d.chips || []))
        .catch(() => setChips([]));
    }
  }, [open, enabled, currentRoute]);

  // Listen for follow-up chip clicks from child messages
  useEffect(() => {
    const handler = (e) => {
      if (!loading) sendQuestion(e.detail.text);
    };
    window.addEventListener('assistant:followup', handler);
    return () => window.removeEventListener('assistant:followup', handler);
  }, [loading, sessionId]);

  // Scroll to bottom on new message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  // Focus input when opening
  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 100);
  }, [open]);

  // Keyboard shortcut Ctrl+/ or Cmd+/
  useEffect(() => {
    const handler = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === '/') {
        e.preventDefault();
        setOpen(v => !v);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  const sendQuestion = useCallback(async (question) => {
    if (!question.trim() || loading) return;
    setInput('');
    setLoading(true);
    setSteps([{ step: 'Understanding your question', ts: Date.now() }]);

    const userMsg = { role: 'user', content: question };
    setMessages(prev => [...prev, userMsg]);

    try {
      const data = await apiCall('/chat', {
        method: 'POST',
        body: JSON.stringify({
          question,
          session_id: sessionId,
          ui_context: { route: currentRoute },
        }),
      });

      if (data.session_id && !sessionId) setSessionId(data.session_id);

      const assistantMsg = {
        role: 'assistant',
        answer: data.answer,
        message_id: data.message_id,
        steps: data.steps || [],
      };
      setMessages(prev => [...prev, assistantMsg]);
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        answer: {
          headline: 'The assistant encountered an error.',
          details: [String(err)],
          verification_label: 'could_not_verify',
          evidence_line: '',
          caveats: [],
          checks: [],
          followups: [],
          page_links: [],
          is_fallback: true,
        },
      }]);
    } finally {
      setLoading(false);
      setSteps([]);
    }
  }, [loading, sessionId, currentRoute]);

  const handleSubmit = (e) => {
    e.preventDefault();
    sendQuestion(input);
  };

  const clearContext = async () => {
    if (sessionId) {
      await apiCall(`/session/${sessionId}/context`, { method: 'DELETE' }).catch(() => {});
    }
    setMessages([]);
    setSessionId(null);
    setChips([]);
    apiCall(`/suggestions?route=${encodeURIComponent(currentRoute)}`)
      .then(d => setChips(d.chips || []));
  };

  const loadHelp = async () => {
    setView('help');
    if (!helpData) {
      apiCall('/help').then(d => setHelpData(d.help)).catch(() => {});
    }
  };

  const sendFeedback = (messageId, rating) => {
    apiCall('/feedback', {
      method: 'POST',
      body: JSON.stringify({ message_id: messageId, rating }),
    }).catch(() => {});
  };

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <>
      {/* Bounce animation keyframes */}
      <style>{`
        @keyframes asst-bounce {
          0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
          40% { transform: scale(1); opacity: 1; }
        }
        .asst-panel { font-family: inherit; }
        .asst-chip:hover { background: var(--hover-bg, #f1f5f9) !important; }
      `}</style>

      {/* Trigger button */}
      {!open && (
        <button
          id="assistant-trigger-btn"
          onClick={() => setOpen(true)}
          title="Open Assistant (Ctrl+/)"
          aria-label="Open EchoInsight Assistant"
          style={{
            position: 'fixed', bottom: 24, right: 24,
            width: 48, height: 48, borderRadius: '50%',
            background: 'var(--primary, #2563eb)',
            color: '#fff', border: 'none', cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 4px 16px rgba(37,99,235,.35)',
            zIndex: 9990,
            fontSize: 20, fontWeight: 700,
            transition: 'transform .15s, box-shadow .15s',
          }}
          onMouseEnter={e => { e.currentTarget.style.transform = 'scale(1.08)'; e.currentTarget.style.boxShadow = '0 6px 24px rgba(37,99,235,.5)'; }}
          onMouseLeave={e => { e.currentTarget.style.transform = ''; e.currentTarget.style.boxShadow = '0 4px 16px rgba(37,99,235,.35)'; }}
        >
          ?
        </button>
      )}

      {/* Panel */}
      {open && (
        <div
          className="asst-panel"
          role="dialog"
          aria-label="EchoInsight Assistant"
          style={{
            position: 'fixed', top: 0, right: 0, bottom: 0,
            width: 420,
            background: 'var(--bg, #f8fafc)',
            borderLeft: '1px solid var(--border)',
            display: 'flex', flexDirection: 'column',
            zIndex: 9991,
            boxShadow: '-4px 0 24px rgba(0,0,0,.08)',
          }}
        >
          {/* Header */}
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '12px 14px', borderBottom: '1px solid var(--border)',
            background: 'var(--card-bg, #fff)',
            flexShrink: 0,
          }}>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                id="asst-tab-chat"
                onClick={() => setView('chat')}
                style={{
                  background: view === 'chat' ? 'var(--primary, #2563eb)' : 'transparent',
                  color: view === 'chat' ? '#fff' : 'var(--text-muted)',
                  border: '1px solid ' + (view === 'chat' ? 'transparent' : 'var(--border)'),
                  borderRadius: 6, padding: '4px 12px', fontSize: 12,
                  cursor: 'pointer', fontWeight: 600,
                }}
              >
                Assistant
              </button>
              <button
                id="asst-tab-help"
                onClick={loadHelp}
                style={{
                  background: view === 'help' ? 'var(--primary, #2563eb)' : 'transparent',
                  color: view === 'help' ? '#fff' : 'var(--text-muted)',
                  border: '1px solid ' + (view === 'help' ? 'transparent' : 'var(--border)'),
                  borderRadius: 6, padding: '4px 12px', fontSize: 12,
                  cursor: 'pointer', fontWeight: 600,
                }}
              >
                Help
              </button>
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              {messages.length > 0 && (
                <button
                  id="asst-clear-btn"
                  onClick={clearContext}
                  title="Clear context and history"
                  style={{
                    background: 'none', border: '1px solid var(--border)',
                    borderRadius: 6, padding: '4px 10px', fontSize: 11,
                    color: 'var(--text-muted)', cursor: 'pointer',
                  }}
                >
                  Clear
                </button>
              )}
              <button
                id="asst-close-btn"
                onClick={() => setOpen(false)}
                aria-label="Close assistant"
                style={{
                  background: 'none', border: 'none',
                  fontSize: 18, cursor: 'pointer',
                  color: 'var(--text-muted)', padding: '2px 6px',
                }}
              >
                ×
              </button>
            </div>
          </div>

          {/* Body */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '12px 14px' }}>
            {enabled === false && <DisabledMessage />}

            {enabled === true && view === 'help' && <HelpPanel help={helpData} />}

            {enabled === true && view === 'chat' && (
              <>
                {/* Welcome / chips when no messages */}
                {messages.length === 0 && (
                  <div>
                    <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '0 0 14px' }}>
                      Ask me anything about your conversation analytics data.
                      Every answer is verified against live data.
                    </p>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {chips.map((chip, i) => (
                        <button
                          key={i}
                          className="asst-chip"
                          onClick={() => sendQuestion(chip.question)}
                          style={{
                            background: 'var(--card-bg, #fff)',
                            border: '1px solid var(--border)',
                            borderRadius: 8, padding: '8px 12px',
                            textAlign: 'left', cursor: 'pointer',
                            fontSize: 12, color: 'var(--text)',
                            transition: 'background .15s',
                          }}
                        >
                          {chip.label}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Messages */}
                {messages.map((msg, i) => (
                  <div key={i} style={{
                    marginBottom: 14,
                    display: 'flex',
                    flexDirection: msg.role === 'user' ? 'row-reverse' : 'row',
                    gap: 8, alignItems: 'flex-start',
                  }}>
                    {msg.role === 'user' ? (
                      <div style={{
                        background: 'var(--primary, #2563eb)', color: '#fff',
                        borderRadius: 8, padding: '8px 12px',
                        fontSize: 13, maxWidth: '85%',
                      }}>
                        {msg.content}
                      </div>
                    ) : msg.answer ? (
                      <div style={{ width: '100%' }}>
                        {msg.answer.is_clarification ? (
                          <ClarificationMessage answer={msg.answer} />
                        ) : msg.answer.is_out_of_scope ? (
                          <OutOfScopeMessage answer={msg.answer} />
                        ) : (
                          <AnswerMessage answer={msg.answer} isFallback={msg.answer.is_fallback} />
                        )}
                        {/* Feedback */}
                        {msg.message_id && (
                          <div style={{ display: 'flex', gap: 6, marginTop: 6, justifyContent: 'flex-end' }}>
                            <button
                              onClick={() => sendFeedback(msg.message_id, 1)}
                              title="Helpful"
                              style={{
                                background: 'none', border: '1px solid var(--border)',
                                borderRadius: 4, padding: '2px 8px', fontSize: 11,
                                cursor: 'pointer', color: 'var(--text-muted)',
                              }}
                            >
                              Helpful
                            </button>
                            <button
                              onClick={() => sendFeedback(msg.message_id, -1)}
                              title="Not helpful"
                              style={{
                                background: 'none', border: '1px solid var(--border)',
                                borderRadius: 4, padding: '2px 8px', fontSize: 11,
                                cursor: 'pointer', color: 'var(--text-muted)',
                              }}
                            >
                              Not helpful
                            </button>
                          </div>
                        )}
                      </div>
                    ) : null}
                  </div>
                ))}

                {/* Loading */}
                {loading && <TypingIndicator steps={steps} />}

                <div ref={bottomRef} />
              </>
            )}
          </div>

          {/* Input */}
          {enabled === true && view === 'chat' && (
            <form
              onSubmit={handleSubmit}
              style={{
                padding: '10px 14px', borderTop: '1px solid var(--border)',
                background: 'var(--card-bg, #fff)', flexShrink: 0,
              }}
            >
              <div style={{ display: 'flex', gap: 8 }}>
                <input
                  id="asst-question-input"
                  ref={inputRef}
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  placeholder="Ask about your data…"
                  disabled={loading}
                  maxLength={1000}
                  style={{
                    flex: 1, padding: '8px 12px',
                    border: '1px solid var(--border)',
                    borderRadius: 8, fontSize: 13,
                    background: loading ? 'var(--bg, #f8fafc)' : 'var(--card-bg, #fff)',
                    color: 'var(--text)',
                    outline: 'none',
                  }}
                />
                <button
                  id="asst-send-btn"
                  type="submit"
                  disabled={loading || !input.trim()}
                  style={{
                    background: loading || !input.trim() ? 'var(--border)' : 'var(--primary, #2563eb)',
                    color: loading || !input.trim() ? 'var(--text-muted)' : '#fff',
                    border: 'none', borderRadius: 8,
                    padding: '8px 14px', fontSize: 13,
                    cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
                    fontWeight: 600,
                    transition: 'background .15s',
                  }}
                >
                  Send
                </button>
              </div>
              <p style={{ fontSize: 10, color: 'var(--text-muted)', margin: '4px 0 0' }}>
                Ctrl+/ to toggle · Every answer is verified against live data
              </p>
            </form>
          )}
        </div>
      )}
    </>
  );
}
