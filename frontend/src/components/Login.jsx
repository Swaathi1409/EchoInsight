import { useState } from 'react';
import { api, setToken } from '../api';
import { Lock, User, Activity } from 'lucide-react';

export default function Login({ onLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true); setError('');
    try {
      const res = await api.login(username, password);
      setToken(res.access_token);
      onLogin();
    } catch (err) {
      setError(err.message || 'Invalid credentials. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-wrap">
      {/* Background decorative blobs */}
      <div style={{
        position: 'fixed', inset: 0, overflow: 'hidden', zIndex: 0, pointerEvents: 'none',
      }}>
        <div style={{
          position: 'absolute', top: '15%', left: '10%', width: 480, height: 480,
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(59,130,246,0.10) 0%, transparent 70%)',
          filter: 'blur(40px)',
        }} />
        <div style={{
          position: 'absolute', bottom: '10%', right: '8%', width: 360, height: 360,
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(167,139,250,0.08) 0%, transparent 70%)',
          filter: 'blur(40px)',
        }} />
      </div>

      <form className="login-card" onSubmit={submit} style={{ position: 'relative', zIndex: 1 }}>
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 28 }}>
          <div style={{
            width: 40, height: 40, borderRadius: 10,
            background: 'linear-gradient(135deg, rgba(59,130,246,0.25) 0%, rgba(167,139,250,0.20) 100%)',
            border: '1px solid rgba(59,130,246,0.30)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Activity size={18} color="var(--accent-hover)" />
          </div>
          <div>
            <h1 style={{ fontSize: 20, fontWeight: 800, letterSpacing: '-0.4px',
              background: 'linear-gradient(135deg, #60a5fa 0%, #a78bfa 100%)',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
              backgroundClip: 'text', margin: 0 }}>
              EchoInsight
            </h1>
            <p style={{ margin: 0, fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>
              Telecom Conversation Intelligence
            </p>
          </div>
        </div>

        <div style={{ marginBottom: 24 }}>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-heading)', margin: 0, letterSpacing: '-0.3px' }}>
            Sign in to your account
          </h2>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 5 }}>
            Enter your credentials to continue
          </p>
        </div>

        {error && (
          <div className="error-banner" style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20 }}>
            <span style={{ fontSize: 15 }}>⚠</span>
            {error}
          </div>
        )}

        <div className="field">
          <label htmlFor="login-username">Username</label>
          <div style={{ position: 'relative' }}>
            <User size={14} style={{ position: 'absolute', left: 11, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)', pointerEvents: 'none' }} />
            <input
              id="login-username"
              className="input"
              style={{ paddingLeft: 32, width: '100%' }}
              value={username}
              onChange={e => setUsername(e.target.value)}
              placeholder="admin"
              autoComplete="username"
              autoFocus
              required
            />
          </div>
        </div>

        <div className="field">
          <label htmlFor="login-password">Password</label>
          <div style={{ position: 'relative' }}>
            <Lock size={14} style={{ position: 'absolute', left: 11, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)', pointerEvents: 'none' }} />
            <input
              id="login-password"
              className="input"
              style={{ paddingLeft: 32, width: '100%' }}
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              autoComplete="current-password"
              required
            />
          </div>
        </div>

        <button
          className="btn btn-primary btn-lg"
          style={{ width: '100%', justifyContent: 'center', marginTop: 10 }}
          disabled={loading}
          type="submit"
        >
          {loading ? (
            <>
              <span style={{ width: 14, height: 14, border: '2px solid rgba(255,255,255,0.3)', borderTopColor: '#fff', borderRadius: '50%', animation: 'spin 0.7s linear infinite', display: 'inline-block' }} />
              Signing in...
            </>
          ) : 'Sign In'}
        </button>

        <div style={{ marginTop: 20, textAlign: 'center', fontSize: 11, color: 'var(--text-muted)' }}>
          Secured · Role-based access control
        </div>
      </form>
    </div>
  );
}
