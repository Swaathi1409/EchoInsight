const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

let _token = localStorage.getItem('token') || '';

export const setToken = (t) => { _token = t; localStorage.setItem('token', t); };
export const clearToken = () => { _token = ''; localStorage.removeItem('token'); };
export const hasToken = () => !!_token;

const headers = (extra = {}) => ({
  'Content-Type': 'application/json',
  ...((_token) ? { Authorization: `Bearer ${_token}` } : {}),
  ...extra,
});

const handle = async (res) => {
  if (res.status === 401 || res.status === 403) { clearToken(); window.location.hash = '#/login'; throw new Error('Unauthorized'); }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail));
  }
  if (res.status === 204) return null;
  return res.json();
};

export const api = {
  login: (username, password) =>
    fetch(`${API}/api/v1/auth/login`, { method: 'POST', headers: headers(), body: JSON.stringify({ username, password }) }).then(handle),

  getConversations: (limit = 50, offset = 0) =>
    fetch(`${API}/api/v1/conversations?limit=${limit}&offset=${offset}`, { headers: headers() }).then(handle),

  getConversation: (id) =>
    fetch(`${API}/api/v1/conversations/${id}`, { headers: headers() }).then(handle),

  createConversation: (channel = 'call') =>
    fetch(`${API}/api/v1/conversations`, { method: 'POST', headers: headers(), body: JSON.stringify({ channel }) }).then(handle),

  appendTurn: (convId, speaker, text, key) =>
    fetch(`${API}/api/v1/conversations/${convId}/turns`, {
      method: 'POST', headers: headers(),
      body: JSON.stringify({ speaker, text, idempotency_key: key }),
    }).then(handle),

  endConversation: (id) =>
    fetch(`${API}/api/v1/conversations/${id}/end`, { method: 'POST', headers: headers() }).then(handle),

  getAnalysis: (id) =>
    fetch(`${API}/api/v1/conversations/${id}/analysis`, { headers: headers() }).then(handle),

  submitTranscript: (body) =>
    fetch(`${API}/api/v1/conversations/submit`, { method: 'POST', headers: headers(), body: JSON.stringify(body) }).then(handle),

  health: () => fetch(`${API}/health`).then(handle),
};
