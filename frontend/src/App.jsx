import { useState, useEffect } from 'react';
import { api, hasToken, clearToken, getToken } from './api';
import Login from './components/Login';
import Dashboard from './components/Dashboard';
import ConversationDetail from './components/ConversationDetail';
import LiveDemo from './components/LiveDemo';
import AdminPanel from './components/AdminPanel';
import ActionLayerShell from './action_layer/ActionLayerShell';
import './action_layer/action_layer.css';
import AssistantPage from './components/AssistantPage';
import { LayoutDashboard, Mic2, LogOut, Activity, Shield, Zap, MessageSquare, Sun, Moon } from 'lucide-react';

function useRoute() {
  const [hash, setHash] = useState(window.location.hash || '#/');
  useEffect(() => {
    const h = () => setHash(window.location.hash || '#/');
    window.addEventListener('hashchange', h);
    return () => window.removeEventListener('hashchange', h);
  }, []);
  return hash;
}

function parseJwt(token) {
  try {
    const base64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    return JSON.parse(atob(base64));
  } catch { return {}; }
}

export default function App() {
  const [authed, setAuthed] = useState(hasToken());
  const hash = useRoute();

  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    if (authed && !hasToken()) {
      setAuthed(false);
    }
    setMobileMenuOpen(false); // Close menu on route change
  }, [hash, authed]);

  if (!authed) return <Login onLogin={() => setAuthed(true)} />;

  const convMatch = hash.match(/^#\/conversation\/(.+)$/);
  const isDemo = hash === '#/demo';
  const isAdmin = hash === '#/admin';
  const isAction    = hash === '#/action' || hash.startsWith('#/action/');
  const isAssistant = hash === '#/assistant';
  const isOverview  = !convMatch && !isDemo && !isAdmin && !isAction && !isAssistant;

  const role = authed ? (parseJwt(getToken()).role || 'agent') : 'agent';
  const isPrivileged = ['admin', 'supervisor'].includes(role);
  const currentUser = { role };

  const navItems = [
    { label: 'Overview',  icon: LayoutDashboard, href: '#/',          active: isOverview },
    { label: 'Live Demo', icon: Mic2,            href: '#/demo',       active: isDemo },
    { label: 'Action',    icon: Zap,             href: '#/action',     active: isAction },
    { label: 'Assistant', icon: MessageSquare,   href: '#/assistant',  active: isAssistant },
    ...(isPrivileged ? [{ label: 'Admin', icon: Shield, href: '#/admin', active: isAdmin }] : []),
  ];

  const logout = () => { clearToken(); setAuthed(false); };

  let topbarTitle = 'Overview';
  if (isDemo)      topbarTitle = 'Live Demo';
  if (isAdmin)     topbarTitle = 'Admin Panel';
  if (isAction)    topbarTitle = 'Action Intelligence';
  if (isAssistant) topbarTitle = 'Assistant';
  if (convMatch)   topbarTitle = `Conversation ${convMatch[1].slice(0, 8)}…`;

  return (
    <div className="layout">
      {/* Mobile overlay */}
      <div 
        className={`sidebar-overlay ${mobileMenuOpen ? 'open' : ''}`}
        onClick={() => setMobileMenuOpen(false)}
      />

      <aside className={`sidebar ${mobileMenuOpen ? 'open' : ''}`}>
        <div className="sidebar-logo">
          <h1>EchoInsight</h1>
          <p>Conversation Intelligence</p>
        </div>
        <nav className="sidebar-nav">
          <div className="nav-section-label">Navigation</div>
          {navItems.map(n => (
            <a key={n.label} href={n.href} style={{ textDecoration: 'none' }}>
              <div className={`nav-item${n.active ? ' active' : ''}`}>
                <n.icon size={15} />
                {n.label}
              </div>
            </a>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 10, padding: '0 12px', display: 'flex', alignItems: 'center', gap: 6 }}>
            <span className={`badge ${role === 'admin' ? 'badge-purple' : role === 'supervisor' ? 'badge-blue' : 'badge-gray'}`} style={{ fontSize: 10 }}>
              {role}
            </span>
          </div>
          <button className="nav-item" onClick={logout} style={{ color: 'var(--red)', width: '100%' }}>
            <LogOut size={15} /> Sign Out
          </button>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div className="topbar-left" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <button className="mobile-menu-btn" onClick={() => setMobileMenuOpen(true)}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="3" y1="12" x2="21" y2="12"></line>
                <line x1="3" y1="6" x2="21" y2="6"></line>
                <line x1="3" y1="18" x2="21" y2="18"></line>
              </svg>
            </button>
            <span className="topbar-title">{topbarTitle}</span>
          </div>
          <div className="topbar-right" style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <ThemeToggle />
            <StatusIndicator />
          </div>
        </header>

        {convMatch
          ? <ConversationDetail convId={convMatch[1]} />
          : isDemo
          ? <LiveDemo />
          : isAdmin
          ? <AdminPanel />
          : isAction
          ? <ActionLayerShell currentUser={currentUser} />
          : isAssistant
          ? <AssistantPage currentRoute={hash} />
          : <Dashboard onSelectConv={(id) => { window.location.hash = `#/conversation/${id}`; }} />
        }
      </main>
    </div>
  );
}

function StatusIndicator() {
  const [ok, setOk] = useState(null);
  const [dbOk, setDbOk] = useState(null);

  useEffect(() => {
    const check = () => {
      api.health().then(() => setOk(true)).catch(() => setOk(false));
      api.ready()
        .then(r => setDbOk(r.database === 'ok'))
        .catch(() => setDbOk(false));
    };
    check();
    const t = setInterval(check, 30000);
    return () => clearInterval(t);
  }, []);

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 12,
        color: ok === null ? 'var(--text-muted)' : ok ? 'var(--green)' : 'var(--red)' }}>
        <Activity size={13} />
        {ok === null ? 'Connecting…' : ok ? 'API Online' : 'API Offline'}
      </div>
      {dbOk !== null && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11,
          color: dbOk ? 'var(--text-muted)' : 'var(--amber)' }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: dbOk ? 'var(--green)' : 'var(--amber)', display: 'inline-block' }} />
          DB {dbOk ? 'OK' : 'Check'}
        </div>
      )}
    </div>
  );
}

function ThemeToggle() {
  const [theme, setTheme] = useState(localStorage.getItem('theme') || 'system');

  useEffect(() => {
    if (theme === 'dark') {
      document.documentElement.setAttribute('data-theme', 'dark');
      localStorage.setItem('theme', 'dark');
    } else if (theme === 'light') {
      document.documentElement.setAttribute('data-theme', 'light');
      localStorage.setItem('theme', 'light');
    } else {
      document.documentElement.removeAttribute('data-theme');
      localStorage.removeItem('theme');
    }
  }, [theme]);

  const toggle = () => {
    if (theme === 'system') {
      const isSystemDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      setTheme(isSystemDark ? 'light' : 'dark');
    } else if (theme === 'dark') {
      setTheme('light');
    } else {
      setTheme('system');
    }
  };

  return (
    <button onClick={toggle} title="Toggle theme" style={{ 
      background: 'none', border: 'none', color: 'var(--text-muted)', 
      cursor: 'pointer', padding: 4, display: 'flex', alignItems: 'center', 
      borderRadius: '4px' 
    }}>
      {theme === 'dark' ? <Moon size={16} /> : theme === 'light' ? <Sun size={16} /> : (
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ fontSize: 10, fontWeight: 600 }}>AUTO</span>
        </div>
      )}
    </button>
  );
}
