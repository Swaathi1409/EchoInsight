import { useState, useEffect } from 'react';
import { api, hasToken, clearToken } from './api';
import Login from './components/Login';
import Dashboard from './components/Dashboard';
import ConversationDetail from './components/ConversationDetail';
import LiveDemo from './components/LiveDemo';
import { LayoutDashboard, Mic2, LogOut, Activity } from 'lucide-react';

function useRoute() {
  const [hash, setHash] = useState(window.location.hash || '#/');
  useEffect(() => {
    const h = () => setHash(window.location.hash || '#/');
    window.addEventListener('hashchange', h);
    return () => window.removeEventListener('hashchange', h);
  }, []);
  return hash;
}

export default function App() {
  const [authed, setAuthed] = useState(hasToken());
  const hash = useRoute();

  if (!authed) return <Login onLogin={() => setAuthed(true)} />;

  // Simple hash router
  const convMatch = hash.match(/^#\/conversation\/(.+)$/);
  const isDemo = hash === '#/demo';

  const navItems = [
    { label: 'Overview', icon: LayoutDashboard, href: '#/', active: !convMatch && !isDemo },
    { label: 'Live Demo', icon: Mic2, href: '#/demo', active: isDemo },
  ];

  const logout = () => { clearToken(); setAuthed(false); };

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <h1>EchoInsight</h1>
          <p>Conversation Intelligence</p>
        </div>
        <nav className="sidebar-nav">
          {navItems.map(n => (
            <a key={n.label} href={n.href} style={{ textDecoration: 'none' }}>
              <div className={`nav-item${n.active ? ' active' : ''}`}>
                <n.icon size={16} /> {n.label}
              </div>
            </a>
          ))}
        </nav>
        <div className="sidebar-footer">
          <button className="nav-item" onClick={logout} style={{ color: 'var(--red)' }}>
            <LogOut size={16} /> Sign Out
          </button>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <span className="topbar-title">
            {isDemo ? 'Live Demo' : convMatch ? 'Conversation' : 'Overview'}
          </span>
          <div className="topbar-right">
            <StatusIndicator />
          </div>
        </header>

        {convMatch
          ? <ConversationDetail convId={convMatch[1]} />
          : isDemo
          ? <LiveDemo />
          : <Dashboard />
        }
      </main>
    </div>
  );
}

function StatusIndicator() {
  const [ok, setOk] = useState(null);
  useEffect(() => {
    api.health().then(() => setOk(true)).catch(() => setOk(false));
    const t = setInterval(() => api.health().then(() => setOk(true)).catch(() => setOk(false)), 30000);
    return () => clearInterval(t);
  }, []);
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: ok === null ? 'var(--text-muted)' : ok ? 'var(--green)' : 'var(--red)' }}>
      <Activity size={14} />
      {ok === null ? 'Connecting…' : ok ? 'API Online' : 'API Offline'}
    </div>
  );
}
