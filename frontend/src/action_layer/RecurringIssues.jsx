// frontend/src/action_layer/RecurringIssues.jsx
// Lists detected recurring issues with metrics, prevention suggestions, and PDCA link.

import { useState, useEffect } from "react";
import { actionApi } from "./api.js";

const TREND_ICONS = { up: "↑", down: "↓", flat: "→", insufficient_data: "?" };
const TREND_COLORS = { up: "#ef4444", down: "#22c55e", flat: "#94a3b8", insufficient_data: "#94a3b8" };

export default function RecurringIssues({ currentUser, onCreateInitiative }) {
  const [issues, setIssues] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState(null);
  const [issueDetail, setIssueDetail] = useState({});

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const data = await actionApi.listIssues();
        setIssues(data.issues || []);
      } catch (e) {
        setError(e?.data?.detail || "Failed to load issues");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const toggleExpand = async (issue) => {
    if (expanded === issue.id) { setExpanded(null); return; }
    setExpanded(issue.id);
    if (!issueDetail[issue.id]) {
      try {
        const d = await actionApi.getIssue(issue.id);
        setIssueDetail((prev) => ({ ...prev, [issue.id]: d }));
      } catch (e) {
        setIssueDetail((prev) => ({
          ...prev,
          [issue.id]: { error: e?.data?.detail || "Failed" },
        }));
      }
    }
  };

  if (loading) return <div className="al-loading-inline">Loading recurring issues…</div>;
  if (error) return <div className="al-error">{error}</div>;

  return (
    <div className="al-pane">
      <div className="al-pane-header">
        <h2>Recurring Issues</h2>
        <p className="al-pane-sub">
          Detected from stored analysis by call reason — volume, unresolved rate, trend, escalation.
          Example policy — owner review required.
        </p>
      </div>

      {issues.length === 0 && (
        <div className="al-empty">
          No recurring issues detected. Run the derive-issues pipeline to analyse conversations.
        </div>
      )}

      <div className="al-issue-list">
        {issues.map((issue) => {
          const isOpen = expanded === issue.id;
          const detail = issueDetail[issue.id];
          return (
            <div key={issue.id} className="al-issue-card">
              <div className="al-issue-card-header" onClick={() => toggleExpand(issue)}>
                <div className="al-issue-title">
                  <span className="al-issue-reason">{issue.reason_label}</span>
                  <span
                    className="al-issue-trend"
                    style={{ color: TREND_COLORS[issue.trend_direction] }}
                    title={`${issue.trend_pct_change != null ? (issue.trend_pct_change > 0 ? "+" : "") + Math.round(issue.trend_pct_change * 100) + "%" : "trend"}`}
                  >
                    {TREND_ICONS[issue.trend_direction]} {issue.trend_direction}
                  </span>
                </div>
                <div className="al-issue-metrics">
                  <MetricPill label="Volume" value={issue.volume} />
                  <MetricPill label="Unresolved" value={`${Math.round(issue.unresolved_rate * 100)}%`} warn={issue.unresolved_rate >= 0.4} />
                  <MetricPill label="Escalation" value={`${Math.round(issue.escalation_share * 100)}%`} warn={issue.escalation_share >= 0.3} />
                  {issue.avg_qa_score != null && <MetricPill label="Avg QA" value={`${issue.avg_qa_score}/100`} />}
                </div>
                <div className="al-issue-thresholds">
                  {issue.triggered_thresholds?.map((t, i) => (
                    <span key={i} className="al-tag-triggered">{t}</span>
                  ))}
                </div>
                <button className="al-expand-btn">{isOpen ? "▲ Collapse" : "▼ Details"}</button>
              </div>

              {isOpen && (
                <div className="al-issue-detail">
                  {!detail && <div className="al-loading-inline">Loading…</div>}
                  {detail?.error && <div className="al-error">{detail.error}</div>}
                  {detail && !detail.error && (
                    <>
                      {/* Example quotes */}
                      {issue.example_quotes?.length > 0 && (
                        <div className="al-issue-quotes">
                          <h4>Example Customer Quotes</h4>
                          {issue.example_quotes.map((q, i) => (
                            <blockquote key={i} className="al-quote">
                              &ldquo;{q.quote}&rdquo;
                              <cite>Conv: {q.conv_id?.slice(0, 12)}&hellip;</cite>
                            </blockquote>
                          ))}
                        </div>
                      )}

                      {/* Prevention suggestions */}
                      {detail.prevention_suggestions?.length > 0 && (
                        <div className="al-prevention">
                          <h4>Prevention Suggestions</h4>
                          <p className="al-prevention-label">
                            Hypothesis for human validation — not a confirmed root cause.
                          </p>
                          {detail.prevention_suggestions.map((s, i) => (
                            <div key={i} className="al-prevention-card">
                              <div className="al-prevention-owner">
                                Suggested owner: <strong>{s.suggested_owner}</strong>
                              </div>
                              <div className="al-prevention-text">{s.suggestion_text}</div>
                              <details className="al-prevention-evidence">
                                <summary>Evidence ({s.evidence?.n} conversations)</summary>
                                <ul>
                                  <li>Unresolved rate: {s.evidence?.unresolved_rate != null ? `${Math.round(s.evidence.unresolved_rate * 100)}%` : "N/A"}</li>
                                  <li>Trend: {s.evidence?.trend_direction}</li>
                                  {s.evidence?.triggered_thresholds?.map((t, j) => <li key={j}>{t}</li>)}
                                </ul>
                              </details>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Link to create initiative */}
                      {(currentUser?.role === "admin" || currentUser?.role === "supervisor") && onCreateInitiative && (
                        <div className="al-issue-actions">
                          <button
                            className="al-btn-secondary"
                            onClick={onCreateInitiative}
                          >
                            Create PDCA Initiative for this issue
                          </button>
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function MetricPill({ label, value, warn = false }) {
  return (
    <span className={`al-metric-pill${warn ? " al-metric-pill--warn" : ""}`}>
      <span className="al-metric-label">{label}</span>
      <span className="al-metric-value">{value}</span>
    </span>
  );
}
