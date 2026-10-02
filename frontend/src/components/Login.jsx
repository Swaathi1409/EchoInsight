import { useState } from 'react';
import { api, setToken } from '../api';
import { Lock, User } from 'lucide-react';

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
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-wrap">
      <form className="login-card" onSubmit={submit}>
        <h1>EchoInsight</h1>
        <p>Telecom Conversation Intelligence Platform</p>
        {error && <div className="error-banner">{error}</div>}
        <div className="field">
          <label>Username</label>
          <div style={{ position: 'relative' }}>
            <User size={14} style={{ position: 'absolute', left: 10, top: 10, color: 'var(--text-muted)' }} />
            <input className="input" style={{ paddingLeft: 30 }} value={username}
              onChange={e => setUsername(e.target.value)} placeholder="admin" required />
          </div>
        </div>
        <div className="field">
          <label>Password</label>
          <div style={{ position: 'relative' }}>
            <Lock size={14} style={{ position: 'absolute', left: 10, top: 10, color: 'var(--text-muted)' }} />
            <input className="input" style={{ paddingLeft: 30 }} type="password" value={password}
              onChange={e => setPassword(e.target.value)} placeholder="password" required />
          </div>
        </div>
        <button className="btn btn-primary" style={{ width: '100%', justifyContent: 'center', marginTop: 8 }}
          disabled={loading} type="submit">
          {loading ? 'Signing in...' : 'Sign in'}
        </button>
      </form>
    </div>
  );
}
