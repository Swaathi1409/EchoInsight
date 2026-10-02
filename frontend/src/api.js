const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

let _token = localStorage.getItem('token') || '';

export const setToken = (t) => { _token = t; localStorage.setItem('token', t); };
export const clearToken = () => { _token = ''; localStorage.removeItem('token'); };
export const hasToken = () => !!_token;
export const getToken = () => _token;

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

  // Conversations list with optional filters
  getConversations: (params = {}) => {
    const qs = new URLSearchParams();
    if (params.limit) qs.set('limit', params.limit);
    if (params.offset) qs.set('offset', params.offset);
    if (params.status) qs.set('status', params.status);
    if (params.agent_id) qs.set('agent_id', params.agent_id);
    if (params.team_id) qs.set('team_id', params.team_id);
    if (params.search) qs.set('search', params.search);
    return fetch(`${API}/api/v1/conversations?${qs}`, { headers: headers() }).then(handle);
  },

  getConversation: (id) =>
    fetch(`${API}/api/v1/conversations/${id}`, { headers: headers() }).then(handle),

  createConversation: (channel = 'call', source_id = '') =>
    fetch(`${API}/api/v1/conversations`, {
      method: 'POST', headers: headers(),
      body: JSON.stringify({ channel, source_id: source_id || undefined }),
    }).then(handle),

  appendTurn: (convId, speaker, text, key) =>
    fetch(`${API}/api/v1/conversations/${convId}/turns`, {
      method: 'POST', headers: headers(),
      body: JSON.stringify({ speaker, text, idempotency_key: key }),
    }).then(handle),

  endConversation: (id) =>
    fetch(`${API}/api/v1/conversations/${id}/end`, { method: 'POST', headers: headers() }).then(handle),

  closeConversation: (id) =>
    fetch(`${API}/api/v1/conversations/${id}/close`, { method: 'POST', headers: headers() }).then(handle),

  submitTranscript: (turns, channel = 'call', source_id = '') =>
    fetch(`${API}/api/v1/conversations/submit`, {
      method: 'POST', headers: headers(),
      body: JSON.stringify({ turns, channel, source_id: source_id || undefined }),
    }).then(handle),

  getJobs: (convId) =>
    fetch(`${API}/api/v1/conversations/${convId}/jobs`, { headers: headers() }).then(handle),

  getOpenCommitments: (limit = 50) =>
    fetch(`${API}/api/v1/conversations/open-commitments?limit=${limit}`, { headers: headers() }).then(handle),

  getFalseResolutions: () =>
    fetch(`${API}/api/v1/conversations/false-resolutions`, { headers: headers() }).then(handle),

  getAgentAnalytics: (agentId) =>
    fetch(`${API}/api/v1/analytics/agent/${agentId}`, { headers: headers() }).then(handle),

  getTeamAnalytics: (teamId) =>
    fetch(`${API}/api/v1/analytics/team/${teamId}`, { headers: headers() }).then(handle),

  // Analytics aggregates for charts
  getConversationStats: () =>
    fetch(`${API}/api/v1/conversations?limit=500`, { headers: headers() }).then(handle),

  // Analysis versioning
  getAnalysis: (convId, version = null) => {
    const qs = version != null ? `?version=${version}` : '';
    return fetch(`${API}/api/v1/conversations/${convId}/analysis${qs}`, { headers: headers() }).then(handle);
  },
  getAnalysisVersions: (convId) =>
    fetch(`${API}/api/v1/conversations/${convId}/analysis/versions`, { headers: headers() }).then(handle),

  // Conversation resumption
  reopenConversation: (convId) =>
    fetch(`${API}/api/v1/conversations/${convId}/reopen`, { method: 'POST', headers: headers() }).then(handle),

  // Reviewer workflow
  createReview: (convId, verdict, notes, qaOverride = {}) =>
    fetch(`${API}/api/v1/conversations/${convId}/reviews`, {
      method: 'POST', headers: headers(),
      body: JSON.stringify({ verdict, notes, qa_override: qaOverride }),
    }).then(handle),
  getReviews: (convId) =>
    fetch(`${API}/api/v1/conversations/${convId}/reviews`, { headers: headers() }).then(handle),

  // Admin: audit logs
  getAuditLogs: (params = {}) => {
    const qs = new URLSearchParams(params);
    return fetch(`${API}/api/v1/audit-logs?${qs}`, { headers: headers() }).then(handle);
  },

  // Admin: checklists
  getChecklists: () =>
    fetch(`${API}/api/v1/checklists`, { headers: headers() }).then(handle),
  getChecklist: (version) =>
    fetch(`${API}/api/v1/checklists/${version}`, { headers: headers() }).then(handle),
  createChecklist: (body) =>
    fetch(`${API}/api/v1/checklists`, { method: 'POST', headers: headers(), body: JSON.stringify(body) }).then(handle),

  // Budget status
  getBudgetStatus: () =>
    fetch(`${API}/budget-status`, { headers: headers() }).then(handle),

  health: () => fetch(`${API}/health`).then(handle),
  ready: () => fetch(`${API}/ready`).then(handle),
  metrics: () => fetch(`${API}/metrics`).then(r => r.text()),
};
