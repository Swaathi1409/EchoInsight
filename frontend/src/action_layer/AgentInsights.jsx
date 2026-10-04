// frontend/src/action_layer/AgentInsights.jsx
// Agent profile viewer — shows computed metrics with disclaimers, n, and bands.

import { useState } from "react";
import { actionApi } from "./api.js";

const BAND_COLORS = { strong: "#22c55e", developing: "#f59e0b", needs_attention: "#ef4444", no_qa_data: "#94a3b8" };

export default function AgentInsights({ currentUser }) {
  const [agentId, setAgentId] = useState("");
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const lookup = async () => {
    if (!agentId.trim()) return;
    setLoading(true);
    setError(null);
    setProfile(null);
    try {
      const data = await actionApi.agentProfile(agentId.trim());
      setProfile(data.profile);
    } catch (e) {
      setError(e?.data?.detail || "Failed to load profile");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="al-pane">
      <div className="al-pane-header">
        <h2>Agent Insights</h2>
        <p className="al-pane-sub">
          Metrics derived from stored analysis — not manual audits. For coaching context only.
        </p>
      </div>

      <div className="al-agent-search">
        <input
          type="text"
          placeholder="Enter agent ID…"
          value={agentId}
          onChange={(e) => setAgentId(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && lookup()}
        />
        <button className="al-btn-primary" onClick={lookup} disabled={loading}>
          {loading ? "Loading…" : "Look up"}
        </button>
      </div>

      {error && <div className="al-error">{error}</div>}

      {profile && !profile.sufficient_data && (
        <div className="al-insufficient">
          <h3>Insufficient Data</h3>
          <p>{profile.message}</p>
        </div>
      )}

      {profile?.sufficient_data && (
        <div className="al-profile">
          <div className="al-profile-header">
            <div className="al-profile-id">Agent: {profile.agent_display}</div>
            {profile.team_id && <div className="al-profile-team">Team: {profile.team_id}</div>}
            <div className="al-profile-n">Based on {profile.metrics.n} conversations · as-of {profile.as_of?.slice(0, 10)}</div>
          </div>

          <div className="al-profile-disclaimer">{profile.disclaimer}</div>

          {/* Bands */}
          <div className="al-profile-bands">
            {Object.entries(profile.bands).map(([k, band]) => (
              <div key={k} className="al-profile-band-card">
                <div className="al-profile-band-label">{k.replace(/_/g, " ")}</div>
                <div className="al-profile-band-value" style={{ color: BAND_COLORS[band] }}>
                  {band.replace(/_/g, " ")}
                </div>
              </div>
            ))}
          </div>

          {/* Key metrics */}
          <div className="al-metrics-grid">
            {[
              { key: "resolution_rate", label: "Resolution Rate", pct: true },
              { key: "unresolved_rate", label: "Unresolved Rate", pct: true },
              { key: "false_resolution_rate", label: "False Resolution Rate", pct: true },
              { key: "avg_qa_score", label: "Avg QA Score" },
              { key: "churn_signal_rate", label: "Churn Signal Rate", pct: true },
              { key: "positive_sentiment_rate", label: "Positive Sentiment", pct: true },
              { key: "negative_sentiment_rate", label: "Negative Sentiment", pct: true },
              { key: "commitment_completion_rate", label: "Commitment Completion", pct: true },
            ].map(({ key, label, pct }) => {
              const val = profile.metrics[key];
              if (val == null) return null;
              return (
                <div key={key} className="al-metric-card">
                  <div className="al-metric-card-label">{label}</div>
                  <div className="al-metric-card-value">
                    {pct ? `${Math.round(val * 100)}%` : val}
                  </div>
                  <div className="al-metric-card-n">n={profile.metrics.n}</div>
                </div>
              );
            })}
          </div>

          {/* Strengths */}
          {profile.strengths?.length > 0 && (
            <div className="al-profile-section al-profile-section--green">
              <h4>Strengths (derived from data)</h4>
              <ul>{profile.strengths.map((s, i) => <li key={i}>{s}</li>)}</ul>
            </div>
          )}

          {/* Development areas */}
          {profile.development_areas?.length > 0 && (
            <div className="al-profile-section al-profile-section--amber">
              <h4>Development Areas (derived from data)</h4>
              <ul>{profile.development_areas.map((d, i) => <li key={i}>{d}</li>)}</ul>
            </div>
          )}

          {/* Top call reasons */}
          {profile.top_call_reasons?.length > 0 && (
            <div className="al-profile-reasons">
              <h4>Top Call Reasons Handled</h4>
              <div className="al-reason-bars">
                {profile.top_call_reasons.map((r, i) => (
                  <div key={i} className="al-reason-bar-row">
                    <span className="al-reason-bar-label">{r.reason}</span>
                    <div className="al-reason-bar">
                      <div
                        className="al-reason-bar-fill"
                        style={{
                          width: `${Math.min(100, (r.count / profile.metrics.n) * 100)}%`,
                        }}
                      />
                    </div>
                    <span className="al-reason-bar-count">{r.count}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Caveats */}
          <details className="al-profile-caveats">
            <summary>Data caveats</summary>
            <ul>{profile.caveats?.map((c, i) => <li key={i}>{c}</li>)}</ul>
          </details>
        </div>
      )}
    </div>
  );
}
