// frontend/src/action_layer/RecoveryDesk.jsx
// Recovery Desk: list of at-risk conversations with priority, risk index,
// intervention type, workflow actions, draft, and what-if.

import { useState, useEffect, useCallback } from "react";
import { actionApi } from "./api.js";
import RiskBreakdown from "./RiskBreakdown.jsx";
import DraftViewer from "./DraftViewer.jsx";

const PRIORITY_COLORS = { P1: "#ef4444", P2: "#f97316", P3: "#64748b" };
const BAND_COLORS = { high: "#ef4444", medium: "#f97316", low: "#22c55e" };
const STATUS_LABELS = {
  new: "New", claimed: "Claimed", contacted: "Contacted",
  recovered: "Recovered", lost: "Lost", dismissed: "Dismissed",
};
const INTERVENTION_LABELS = {
  fix_driven: "Fix-Driven",
  price_sensitive: "Price-Sensitive",
  relationship_repair: "Relationship Repair",
  firm_exit_intent: "Firm Exit Intent",
  monitor: "Monitor",
  undetermined: "Undetermined",
};

function PriorityBadge({ p }) {
  return (
    <span className="al-badge-priority" style={{ background: PRIORITY_COLORS[p] || "#64748b" }}>
      {p}
    </span>
  );
}

function RiskMeter({ value, band }) {
  return (
    <div className="al-risk-meter" title={`Risk index: ${value}/10 (${band})`}>
      <div className="al-risk-meter-fill"
        style={{
          width: `${value * 10}%`,
          background: BAND_COLORS[band] || "#64748b",
        }}
      />
      <span className="al-risk-meter-label">{value}/10</span>
    </div>
  );
}

const NEXT_TRANSITIONS = {
  new: ["claimed", "dismissed"],
  claimed: ["contacted", "dismissed"],
  contacted: ["recovered", "lost", "dismissed"],
  recovered: ["claimed"],
  lost: ["claimed"],
  dismissed: ["claimed"],
};

export default function RecoveryDesk({ currentUser }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState({ priority: "", status: "", interventionType: "" });
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [view, setView] = useState("list"); // list | detail | draft | whatif
  const [draft, setDraft] = useState(null);
  const [whatIfResult, setWhatIfResult] = useState(null);
  const [transitioning, setTransitioning] = useState(false);
  const [transitionModal, setTransitionModal] = useState(null);
  const [transitionForm, setTransitionForm] = useState({ notes: "", outcome: "", dismissal_reason: "" });
  const [transitionError, setTransitionError] = useState("");
  const [draftEditForm, setDraftEditForm] = useState({ status: "", owner: "", notes: "" });
  const [draftSaving, setDraftSaving] = useState(false);
  const [draftSaveMsg, setDraftSaveMsg] = useState("");

  const loadItems = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await actionApi.listItems(filters);
      setItems(data.items || []);
    } catch (e) {
      setError(e?.data?.detail || "Failed to load items");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => { loadItems(); }, [loadItems]);

  const openDetail = async (item) => {
    setSelected(item);
    setView("detail");
    setDetail(null);
    setDraft(null);
    setWhatIfResult(null);
    setDetailLoading(true);
    try {
      const d = await actionApi.getItem(item.id);
      setDetail(d);
    } catch (e) {
      setDetail({ error: e?.data?.detail || "Failed" });
    } finally {
      setDetailLoading(false);
    }
  };

  const openDraft = async () => {
    setView("draft");
    setDraftSaveMsg("");
    setDraftEditForm({ status: selected?.status || "", owner: "", notes: "" });
    if (draft) return;
    try {
      const d = await actionApi.getDraft(selected.id);
      setDraft(d.draft);
    } catch (e) {
      setDraft({ error: e?.data?.detail || "No draft" });
    }
  };

  const saveDraftEdit = async () => {
    if (!selected) return;
    setDraftSaving(true);
    setDraftSaveMsg("");
    try {
      const toStatus = draftEditForm.status && draftEditForm.status !== selected.status
        ? draftEditForm.status : null;
      const noteText = [
        draftEditForm.owner ? `Owner: ${draftEditForm.owner}` : "",
        draftEditForm.notes || "",
      ].filter(Boolean).join(" | ");
      if (toStatus) {
        await actionApi.transitionItem(selected.id, {
          to_status: toStatus,
          notes: noteText || null,
          outcome: null,
          dismissal_reason: null,
        });
        setSelected((s) => ({ ...s, status: toStatus }));
        setDraftEditForm((f) => ({ ...f, status: toStatus }));
        await loadItems();
      }
      setDraftSaveMsg(toStatus ? `Status updated to "${STATUS_LABELS[toStatus] || toStatus}"` : "Saved.");
    } catch (e) {
      const msg = e?.data?.detail;
      setDraftSaveMsg(`Error: ${typeof msg === "string" ? msg : JSON.stringify(msg) || "Save failed"}`);
    } finally {
      setDraftSaving(false);
    }
  };

  const runWhatIf = async (clearComponents) => {
    try {
      const r = await actionApi.whatIf(selected.id, clearComponents);
      setWhatIfResult(r.scenario);
      setView("whatif");
    } catch (e) {
      alert("What-if failed: " + (e?.data?.detail || "Error"));
    }
  };

  const startTransition = (toStatus) => {
    setTransitionModal(toStatus);
    setTransitionForm({ notes: "", outcome: "", dismissal_reason: "" });
    setTransitionError("");
  };

  const doTransition = async () => {
    setTransitioning(true);
    setTransitionError("");
    try {
      await actionApi.transitionItem(selected.id, {
        to_status: transitionModal,
        notes: transitionForm.notes,
        outcome: transitionForm.outcome || null,
        dismissal_reason: transitionForm.dismissal_reason || null,
      });
      setTransitionModal(null);
      // Refresh
      await loadItems();
      const updated = await actionApi.getItem(selected.id);
      setDetail(updated);
      setSelected((s) => ({ ...s, status: transitionModal }));
    } catch (e) {
      const msg = e?.data?.detail;
      setTransitionError(
        typeof msg === "object" ? msg.message : (msg || "Transition failed")
      );
    } finally {
      setTransitioning(false);
    }
  };

  const filterChanged = (key, val) => {
    setFilters((f) => ({ ...f, [key]: val }));
    setView("list");
  };

  // ── List view ────────────────────────────────────────────────────────────────
  if (view === "list" || !selected) {
    return (
      <div className="al-pane">
        <div className="al-pane-header">
          <h2>Recovery Desk</h2>
          <p className="al-pane-sub">
            Conversations requiring action — derived from stored analysis, no fabrication.
          </p>
        </div>

        <div className="al-filters">
          {[
            { key: "priority", label: "Priority", opts: ["", "P1", "P2", "P3"] },
            { key: "status", label: "Status", opts: ["", ...Object.keys(STATUS_LABELS)] },
            {
              key: "interventionType", label: "Intervention",
              opts: ["", "fix_driven", "price_sensitive", "relationship_repair", "firm_exit_intent", "monitor", "undetermined"],
            },
          ].map(({ key, label, opts }) => (
            <div className="al-filter" key={key}>
              <label>{label}</label>
              <select value={filters[key]} onChange={(e) => filterChanged(key, e.target.value)}>
                {opts.map((o) => (
                  <option key={o} value={o}>
                    {o === "" ? "All" : (key === "interventionType" ? INTERVENTION_LABELS[o] : o)}
                  </option>
                ))}
              </select>
            </div>
          ))}
          <button className="al-btn-secondary" onClick={loadItems}>Refresh</button>
        </div>

        {loading && <div className="al-loading-inline">Loading…</div>}
        {error && <div className="al-error">{error}</div>}

        {!loading && items.length === 0 && (
          <div className="al-empty">
            No items match the current filters. Try adjusting the filters or running the derive pipeline.
          </div>
        )}

        <div className="al-item-list">
          {items.map((item) => (
            <div
              key={item.id}
              className={`al-item-card al-item-card--${item.risk_band}`}
              onClick={() => openDetail(item)}
            >
              <div className="al-item-card-top">
                <PriorityBadge p={item.priority} />
                <span className="al-item-status">{STATUS_LABELS[item.status] || item.status}</span>
                <span className="al-item-intervention">{INTERVENTION_LABELS[item.intervention_type] || item.intervention_type}</span>
              </div>
              <div className="al-item-card-mid">
                <span className="al-item-conv-id" title={item.conversation_id}>
                  Conv: {item.conversation_id?.slice(0, 12)}&hellip;
                </span>
                <RiskMeter value={item.risk_index} band={item.risk_band} />
              </div>
              <div className="al-item-card-bottom">
                <span className="al-item-quadrant">{item.quadrant}</span>
                {!item.evidence_complete && (
                  <span className="al-badge-warn" title="Some signals could not be verified">
                    Evidence incomplete
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // ── Detail / Draft / What-If view ─────────────────────────────────────────────
  const item = selected;

  return (
    <div className="al-pane">
      <div className="al-detail-nav">
        <button className="al-btn-ghost" onClick={() => { setView("list"); setSelected(null); }}>
          &larr; Back to list
        </button>
        <div className="al-detail-subtabs">
          {[
            { id: "detail", label: "Detail" },
            { id: "draft", label: "Follow-up Draft" },
            { id: "whatif", label: "What-If" },
          ].map((t) => (
            <button
              key={t.id}
              className={`al-subtab${view === t.id ? " al-subtab--active" : ""}`}
              onClick={() => t.id === "draft" ? openDraft() : setView(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {view === "detail" && (
        <div className="al-detail">
          <div className="al-detail-header">
            <PriorityBadge p={item.priority} />
            <span className="al-detail-status">{STATUS_LABELS[item.status]}</span>
            <span className="al-detail-conv">
              Conv: <a href={`#/conversations/${item.conversation_id}`}>{item.conversation_id?.slice(0, 16)}&hellip;</a>
            </span>
          </div>

          <div className="al-detail-row">
            <div className="al-detail-block">
              <div className="al-detail-label">Risk Index</div>
              <div className="al-detail-value">
                <RiskMeter value={item.risk_index} band={item.risk_band} />
                <span className="al-detail-disclaimer">
                  Not a probability — weighted sum of recorded signals.
                </span>
              </div>
            </div>
            <div className="al-detail-block">
              <div className="al-detail-label">Intervention Type</div>
              <div className="al-detail-value al-detail-intervention">
                {INTERVENTION_LABELS[item.intervention_type]}
              </div>
            </div>
            <div className="al-detail-block">
              <div className="al-detail-label">Priority</div>
              <div className="al-detail-value">{item.quadrant}</div>
            </div>
          </div>

          {!item.evidence_complete && (
            <div className="al-alert-warn">
              Some signals could not be verified from stored turn data:{" "}
              {item.evidence_incomplete_reasons?.join("; ")}
            </div>
          )}

          {detailLoading && <div className="al-loading-inline">Loading detail…</div>}

          {detail && !detail.error && (
            <>
              <RiskBreakdown components={detail.risk_components} />
              <div className="al-recommendations">
                <h3>Recommended Actions</h3>
                <p className="al-rec-disclaimer">
                  Example playbook — owner review required before production use.
                </p>
                {detail.recommendations?.map((r, i) => (
                  <div key={i} className="al-rec-card">
                    <div className="al-rec-rank">#{r.rank}</div>
                    <div className="al-rec-body">
                      <div className="al-rec-title">{r.title}</div>
                      <div className="al-rec-justification">{r.justification}</div>
                      <div className="al-rec-constraint">{r.constraint_note}</div>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          <div className="al-workflow">
            <h3>Workflow</h3>
            <div className="al-workflow-actions">
              {(NEXT_TRANSITIONS[item.status] || []).map((toStatus) => (
                <button
                  key={toStatus}
                  className={`al-btn-action al-btn-action--${toStatus}`}
                  onClick={() => startTransition(toStatus)}
                >
                  {toStatus === "recovered" ? "Mark Recovered" :
                   toStatus === "lost" ? "Mark Lost" :
                   toStatus === "claimed" ? "Claim / Reopen" :
                   toStatus === "contacted" ? "Log Contact" :
                   toStatus === "dismissed" ? "Dismiss" : toStatus}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {view === "draft" && (
        <div className="al-draft-tab">
          <DraftViewer draft={draft} />

          {currentUser && (currentUser.role === "admin" || currentUser.role === "supervisor") && (
            <div className="al-draft-edit">
              <h4 className="al-draft-edit-title">Workflow Update</h4>
              <div className="al-draft-edit-row">
                <div className="al-form-group">
                  <label>Owner / Assignee</label>
                  <input
                    type="text"
                    placeholder="e.g. Jane Smith"
                    value={draftEditForm.owner}
                    onChange={(e) => setDraftEditForm((f) => ({ ...f, owner: e.target.value }))}
                  />
                </div>
                <div className="al-form-group">
                  <label>Status</label>
                  <select
                    value={draftEditForm.status}
                    onChange={(e) => setDraftEditForm((f) => ({ ...f, status: e.target.value }))}
                  >
                    <option value="">— No change —</option>
                    {(NEXT_TRANSITIONS[selected?.status] || []).map((s) => (
                      <option key={s} value={s}>{STATUS_LABELS[s] || s}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="al-form-group">
                <label>Notes</label>
                <textarea
                  rows={3}
                  placeholder="Optional notes for audit log"
                  value={draftEditForm.notes}
                  onChange={(e) => setDraftEditForm((f) => ({ ...f, notes: e.target.value }))}
                />
              </div>
              <div className="al-draft-edit-actions">
                <button className="al-btn-primary" onClick={saveDraftEdit} disabled={draftSaving}>
                  {draftSaving ? "Saving…" : "Save Changes"}
                </button>
                {draftSaveMsg && (
                  <span className={`al-draft-save-msg${draftSaveMsg.startsWith("Error") ? " al-draft-save-msg--error" : ""}`}>
                    {draftSaveMsg}
                  </span>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {view === "whatif" && (
        <WhatIfPanel
          detail={detail}
          whatIfResult={whatIfResult}
          onRun={runWhatIf}
        />
      )}

      {/* Transition Modal */}
      {transitionModal && (
        <div className="al-modal-overlay" onClick={() => setTransitionModal(null)}>
          <div className="al-modal" onClick={(e) => e.stopPropagation()}>
            <h3>
              {transitionModal === "dismissed" ? "Dismiss Item" :
               transitionModal === "recovered" ? "Record Recovery" :
               transitionModal === "lost" ? "Record Loss" :
               `Move to: ${STATUS_LABELS[transitionModal]}`}
            </h3>

            {(transitionModal === "recovered" || transitionModal === "lost") && (
              <div className="al-form-group">
                <label>Outcome</label>
                <select
                  value={transitionForm.outcome}
                  onChange={(e) => setTransitionForm((f) => ({ ...f, outcome: e.target.value }))}
                >
                  <option value="">Select outcome</option>
                  <option value="retained">Retained</option>
                  <option value="left">Left</option>
                  <option value="no_response">No Response</option>
                  <option value="unknown">Unknown</option>
                </select>
              </div>
            )}

            {transitionModal === "dismissed" && (
              <div className="al-form-group">
                <label>Reason (required)</label>
                <input
                  type="text"
                  placeholder="Why is this being dismissed?"
                  value={transitionForm.dismissal_reason}
                  onChange={(e) => setTransitionForm((f) => ({ ...f, dismissal_reason: e.target.value }))}
                />
              </div>
            )}

            <div className="al-form-group">
              <label>Notes (optional)</label>
              <textarea
                rows={3}
                value={transitionForm.notes}
                onChange={(e) => setTransitionForm((f) => ({ ...f, notes: e.target.value }))}
              />
            </div>

            {transitionError && <div className="al-error">{transitionError}</div>}

            <div className="al-modal-actions">
              <button className="al-btn-ghost" onClick={() => setTransitionModal(null)}>Cancel</button>
              <button
                className="al-btn-primary"
                onClick={doTransition}
                disabled={transitioning}
              >
                {transitioning ? "Saving…" : "Confirm"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function WhatIfPanel({ detail, whatIfResult, onRun }) {
  const [selected, setSelected] = useState([]);
  const components = (detail?.risk_components || []).filter((c) => c.triggered);

  const toggle = (name) => {
    setSelected((s) =>
      s.includes(name) ? s.filter((n) => n !== name) : [...s, name]
    );
  };

  return (
    <div className="al-whatif">
      <h3>What-If Scenario</h3>
      <p className="al-whatif-desc">
        Select risk components to &ldquo;clear&rdquo; and see the hypothetical revised Risk Index.
        This is a scenario tool, not a forecast of customer behavior.
      </p>

      <div className="al-whatif-components">
        {components.map((c) => (
          <label key={c.name} className="al-whatif-check">
            <input
              type="checkbox"
              checked={selected.includes(c.name)}
              onChange={() => toggle(c.name)}
            />
            <span>{c.name} <em>(+{c.points})</em></span>
          </label>
        ))}
        {components.length === 0 && (
          <p className="al-empty">No triggered components found.</p>
        )}
      </div>

      <button
        className="al-btn-primary"
        onClick={() => onRun(selected)}
        disabled={selected.length === 0}
      >
        Run Scenario
      </button>

      {whatIfResult && (
        <div className="al-whatif-result">
          <div className="al-whatif-result-header">
            Scenario Result:{" "}
            <strong>{whatIfResult.scenario_risk_index}/10</strong>{" "}
            <span style={{ color: BAND_COLORS[whatIfResult.scenario_risk_band] }}>
              {whatIfResult.scenario_risk_band}
            </span>
          </div>
          <p className="al-detail-disclaimer">{whatIfResult.disclaimer}</p>
        </div>
      )}
    </div>
  );
}
