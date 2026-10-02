import { useState } from 'react';
import { api } from '../api';
import { Send, Plus, PhoneOff, Mic } from 'lucide-react';

let _idKey = 0;
const nextKey = () => `demo-${Date.now()}-${++_idKey}`;

export default function LiveDemo() {
  const [convId, setConvId] = useState(null);
  const [turns, setTurns] = useState([]);
  const [speaker, setSpeaker] = useState('agent');
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [ended, setEnded] = useState(false);
  const [msg, setMsg] = useState('');
  const [jobId, setJobId] = useState(null);

  const createConv = async () => {
    setLoading(true); setMsg('');
    try {
      const c = await api.createConversation('call');
      setConvId(c.id);
      setTurns([]);
      setEnded(false);
      setJobId(null);
      setMsg(`Conversation created: ${c.id.slice(0, 8)}`);
    } catch (e) { setMsg(`Error: ${e.message}`); }
    finally { setLoading(false); }
  };

  const appendTurn = async () => {
    if (!convId || !text.trim()) return;
    setLoading(true);
    try {
      const res = await api.appendTurn(convId, speaker, text, nextKey());
      setTurns(prev => [...prev, { ...res, text_original: text }]);
      setText('');
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

  const addQuick = async (t) => {
    if (!convId || ended) return;
    setLoading(true);
    try {
      const res = await api.appendTurn(convId, t.speaker, t.text, nextKey());
      setTurns(prev => [...prev, res]);
    } catch (e) { setMsg(`Error: ${e.message}`); }
    finally { setLoading(false); }
  };

  return (
    <div className="page">
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: 20, fontWeight: 700 }}>Live Demo</h2>
        <p style={{ color: 'var(--text-muted)', fontSize: 13, marginTop: 4 }}>
          Create a conversation, add turns, and end it to queue analysis.
        </p>
      </div>

      {msg && <div className="error-banner" style={{ background: msg.startsWith('Error') ? 'var(--red-bg)' : 'var(--green-bg)', borderColor: msg.startsWith('Error') ? 'var(--red)' : 'var(--green)', color: msg.startsWith('Error') ? 'var(--red)' : 'var(--green)' }}>{msg}</div>}

      <div className="grid-2">
        {/* Controls */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="card">
            <div className="card-header"><span className="card-title">Session</span></div>
            <button className="btn btn-primary" onClick={createConv} disabled={loading} style={{ marginBottom: 12 }}>
              <Plus size={14} /> New Conversation
            </button>
            {convId && (
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12, fontFamily: 'monospace', padding: '6px 10px', background: 'var(--bg-secondary)', borderRadius: 4 }}>
                {convId}
              </div>
            )}
            {convId && !ended && (
              <button className="btn btn-ghost" style={{ borderColor: 'var(--red)', color: 'var(--red)' }} onClick={endConv} disabled={loading}>
                <PhoneOff size={14} /> End Conversation
              </button>
            )}
            {jobId && (
              <div style={{ marginTop: 12, fontSize: 12, color: 'var(--amber)', display: 'flex', alignItems: 'center', gap: 6 }}>
                Analysis queued. <button className="btn btn-ghost btn-sm" onClick={() => { window.location.hash = `#/conversation/${convId}`; }}>View</button>
              </div>
            )}
          </div>

          <div className="card">
            <div className="card-header"><span className="card-title">Quick Script</span></div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 300, overflowY: 'auto' }}>
              {QUICK_TURNS.map((t, i) => (
                <button key={i} className="btn btn-ghost btn-sm" style={{ justifyContent: 'flex-start', textAlign: 'left', fontSize: 11 }}
                  onClick={() => addQuick(t)} disabled={!convId || ended || loading}>
                  <span className={`badge ${t.speaker === 'agent' ? 'badge-blue' : 'badge-purple'}`} style={{ minWidth: 60 }}>{t.speaker}</span>
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t.text.slice(0, 50)}…</span>
                </button>
              ))}
            </div>
          </div>

          {/* Manual Turn */}
          {convId && !ended && (
            <div className="card">
              <div className="card-header"><span className="card-title">Manual Turn</span></div>
              <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
                {['agent', 'customer'].map(s => (
                  <button key={s} className={`btn ${speaker === s ? 'btn-primary' : 'btn-ghost'} btn-sm`} onClick={() => setSpeaker(s)} style={{ textTransform: 'capitalize' }}>{s}</button>
                ))}
              </div>
              <textarea className="input" value={text} onChange={e => setText(e.target.value)}
                placeholder="Enter turn text..." rows={3} style={{ width: '100%', resize: 'vertical', marginBottom: 10 }}
                onKeyDown={e => { if (e.key === 'Enter' && e.ctrlKey) appendTurn(); }} />
              <button className="btn btn-primary" onClick={appendTurn} disabled={!text.trim() || loading}>
                <Send size={14} /> Send Turn
              </button>
            </div>
          )}
        </div>

        {/* Transcript Preview */}
        <div className="card" style={{ maxHeight: 600, overflowY: 'auto' }}>
          <div className="card-header"><span className="card-title">Transcript Preview</span>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{turns.length} turns</span>
          </div>
          {turns.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>
              <Mic size={24} style={{ marginBottom: 8, opacity: 0.4 }} />
              <p>No turns yet. Create a conversation and add turns.</p>
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
    </div>
  );
}
