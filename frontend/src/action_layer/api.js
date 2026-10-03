// frontend/src/action_layer/api.js
// API client for the Action Intelligence Layer.

import { getToken } from "../api.js";

const BASE = "/api/v1/action";
const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function apiCall(path, options = {}) {
  const token = getToken();
  const headers = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
  const res = await fetch(`${API_BASE}${BASE}${path}`, { ...options, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw { status: res.status, data };
  return data;
}


export const actionApi = {
  status: () => apiCall("/status"),
  settings: () => apiCall("/settings"),
  updateSettings: (body) =>
    apiCall("/settings", { method: "POST", body: JSON.stringify(body) }),
  seedDemo: () => apiCall("/seed-demo", { method: "POST" }),
  derive: (force = false) =>
    apiCall(`/derive?force=${force}`, { method: "POST" }),
  deriveIssues: () => apiCall("/derive-issues", { method: "POST" }),

  // Items
  listItems: (params = {}) => {
    const q = new URLSearchParams(
      Object.fromEntries(
        Object.entries({
          priority: params.priority,
          status: params.status,
          intervention_type: params.interventionType,
          risk_band: params.riskBand,
          limit: params.limit || 50,
          offset: params.offset || 0,
        }).filter(([, v]) => v !== undefined && v !== null && v !== "")
      )
    ).toString();
    return apiCall(`/items${q ? "?" + q : ""}`);
  },
  getItem: (id) => apiCall(`/items/${id}`),
  transitionItem: (id, body) =>
    apiCall(`/items/${id}/transition`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getDraft: (id) => apiCall(`/items/${id}/draft`),
  whatIf: (id, clearComponents) =>
    apiCall(`/items/${id}/what-if`, {
      method: "POST",
      body: JSON.stringify({ clear_components: clearComponents }),
    }),

  // Issues
  listIssues: () => apiCall("/issues"),
  getIssue: (id) => apiCall(`/issues/${id}`),

  // Initiatives
  listInitiatives: (stage) =>
    apiCall(`/initiatives${stage ? `?stage=${stage}` : ""}`),
  getInitiative: (id) => apiCall(`/initiatives/${id}`),
  createInitiative: (body) =>
    apiCall("/initiatives", { method: "POST", body: JSON.stringify(body) }),
  updateInitiative: (id, body) =>
    apiCall(`/initiatives/${id}`, { method: "PUT", body: JSON.stringify(body) }),

  // Agent
  agentProfile: (agentId) => apiCall(`/agents/${agentId}/profile`),
};
