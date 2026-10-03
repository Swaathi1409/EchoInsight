// frontend/src/action_layer/Initiatives.jsx
// PDCA Initiatives: list, create, and advance through Plan→Do→Check→Act stages.

import { useState, useEffect } from "react";
import { actionApi } from "./api.js";

const STAGES = ["plan", "do", "check", "act"];
const STAGE_LABELS = { plan: "Plan", do: "Do", check: "Check", act: "Act" };
const STAGE_COLORS = { plan: "#6366f1", do: "#0ea5e9", check: "#f59e0b", act: "#22c55e" };

export default function Initiatives({ currentUser }) {
  const [initiatives, setInitiatives] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [stageFilter, setStageFilter] = useState("");
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [updateForm, setUpdateForm] = useState({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const data = await actionApi.listInitiatives(stageFilter);
      setInitiatives(data.initiatives || []);
    } catch (e) {
      setError(e?.data?.detail || "Failed");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [stageFilter]);

  const openDetail = async (ini) => {
    setSelected(ini);
    setDetail(null);
    setDetailLoading(true);
    setUpdateForm({});
    setSaveError("");
    try {
      const d = await actionApi.getInitiative(ini.id);
      setDetail(d);
    } catch (e) {
      setDetail({ error: e?.data?.detail || "Failed" });
    } finally {
      setDetailLoading(false);
    }
  };

  const canEdit = currentUser?.role === "admin" || currentUser?.role === "supervisor";

  const saveUpdate = async () => {
    if (!selected) return;
    setSaving(true);
    setSaveError("");
    try {
      await actionApi.updateInitiative(selected.id, updateForm);
      await load();
      const d = await actionApi.getInitiative(selected.id);
      setDetail(d);
      setUpdateForm({});
    } catch (e) {
      const msg = e?.data?.detail;
      setSaveError(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setSaving(false);
    }
  };

  const advanceStage = (currentStage) => {
    const idx = STAGES.indexOf(currentStage);
    if (idx < STAGES.length - 1) {
      setUpdateForm((f) => ({ ...f, stage: STAGES[idx + 1] }));
    }
  };

  if (loading && initiatives.length === 0) {
    return <div className="al-loading-inline">Loading initiatives…</div>;
  }

  return (
    <div className="al-pane">
      <div className="al-pane-header">
        <div>
          <h2>PDCA Initiatives</h2>
          <p className="al-pane-sub">
            Plan, Do, Check, Act improvement cycles. Check metrics are computed automatically
            once sufficient post-implementation data is available.
          </p>
        </div>
        {canEdit && (
          <button className="al-btn-primary" onClick={() => setShowCreate(true)}>
            + New Initiative
          </button>
        )}
      </div>

      {/* Stage tabs */}
      <div className="al-stage-tabs">
        <button
          className={`al-stage-tab${stageFilter === "" ? " al-stage-tab--active" : ""}`}
          onClick={() => setStageFilter("")}
        >
          All
        </button>
        {STAGES.map((s) => (
          <button
            key={s}
            className={`al-stage-tab${stageFilter === s ? " al-stage-tab--active" : ""}`}
            style={stageFilter === s ? { borderColor: STAGE_COLORS[s], color: STAGE_COLORS[s] } : {}}
            onClick={() => setStageFilter(s)}
          >
            {STAGE_LABELS[s]}
          </button>
        ))}
      </div>

      {error && <div className="al-error">{error}</div>}

      <div className="al-initiative-layout">
        {/* List */}
        <div className="al-initiative-list">
          {initiatives.length === 0 && !loading && (
            <div className="al-empty">No initiatives. Create one from a recurring issue.</div>
          )}
          {initiatives.map((ini) => (
            <div
              key={ini.id}
              className={`al-initiative-card${selected?.id === ini.id ? " al-initiative-card--selected" : ""}`}
              onClick={() => openDetail(ini)}
            >
              <div className="al-initiative-card-top">
                <span
                  className="al-stage-badge"
                  style={{ background: STAGE_COLORS[ini.stage] }}
                >
                  {STAGE_LABELS[ini.stage]}
                </span>
                {ini.demonstration && (
                  <span className="al-demo-badge" title="Demo data — not a real production record">
                    DEMO
                  </span>
                )}
              </div>
              <div className="al-initiative-title">{ini.title}</div>
              <div className="al-initiative-meta">
                <span>Owner: {ini.owner || "—"}</span>
                {ini.due_date && <span>Due: {ini.due_date.slice(0, 10)}</span>}
              </div>
              {ini.check_sufficient_data && (
                <div className="al-initiative-check-badge">
                  Check data available
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Detail panel */}
        {selected && (
          <div className="al-initiative-detail">
            {detailLoading && <div className="al-loading-inline">Loading…</div>}
            {detail?.error && <div className="al-error">{detail.error}</div>}
            {detail && !detail.error && (
              <InitiativeDetail
                ini={detail.initiative}
                history={detail.stage_history}
                canEdit={canEdit}
                updateForm={updateForm}
                setUpdateForm={setUpdateForm}
                onSave={saveUpdate}
                saving={saving}
                saveError={saveError}
                onAdvanceStage={advanceStage}
              />
            )}
          </div>
        )}
      </div>

      {showCreate && (
        <CreateInitiativeModal
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); load(); }}
        />
      )}
    </div>
  );
}

function InitiativeDetail({ ini, history, canEdit, updateForm, setUpdateForm, onSave, saving, saveError, onAdvanceStage }) {
  const u = (key, val) => setUpdateForm((f) => ({ ...f, [key]: val }));
  const stage = updateForm.stage || ini.stage;
  const stageIdx = STAGES.indexOf(stage);

  return (
    <div className="al-ini-detail">
      <div className="al-ini-detail-header">
        <h3>{ini.title}</h3>
        {ini.demonstration && (
          <div className="al-demo-notice">
            DEMONSTRATION DATA — not a real production record.
          </div>
        )}
      </div>

      {/* PDCA Stage progress */}
      <div className="al-pdca-progress">
        {STAGES.map((s, i) => (
          <div
            key={s}
            className={`al-pdca-step ${i <= STAGES.indexOf(stage) ? "al-pdca-step--done" : ""}`}
            style={i === STAGES.indexOf(stage) ? { borderColor: STAGE_COLORS[s] } : {}}
          >
            <div className="al-pdca-step-label" style={{ color: STAGE_COLORS[s] }}>
              {STAGE_LABELS[s]}
            </div>
          </div>
        ))}
      </div>

      {/* Plan fields */}
      <Section label="Plan">
        <FieldRow label="Problem statement" value={ini.problem_statement} />
        <FieldRow label="Root cause hypothesis" value={ini.root_cause_hypothesis} />
        <FieldRow label="Target metric" value={ini.target_metric} />
        <FieldRow label="Target change" value={ini.target_change} />
        {ini.baseline_metrics && (
          <details className="al-detail-block">
            <summary>Baseline metrics</summary>
            <pre className="al-pre">{JSON.stringify(ini.baseline_metrics, null, 2)}</pre>
          </details>
        )}
      </Section>

      {/* Do fields */}
      {stageIdx >= 1 && (
        <Section label="Do">
          {canEdit ? (
            <>
              <EditField label="Implementation description"
                value={updateForm.implementation_description ?? ini.implementation_description}
                onChange={(v) => u("implementation_description", v)} multiline />
              <EditField label="Implementation date (ISO)"
                value={updateForm.implementation_date ?? (ini.implementation_date?.slice(0, 10) || "")}
                onChange={(v) => u("implementation_date", v)} />
              <EditField label="Do owner"
                value={updateForm.do_owner ?? ini.do_owner}
                onChange={(v) => u("do_owner", v)} />
              <div className="al-form-group">
                <label>Do status</label>
                <select
                  value={updateForm.do_status ?? ini.do_status ?? ""}
                  onChange={(e) => u("do_status", e.target.value)}
                >
                  {["", "planned", "in_progress", "completed", "blocked"].map((o) => (
                    <option key={o} value={o}>{o || "—"}</option>
                  ))}
                </select>
              </div>
            </>
          ) : (
            <>
              <FieldRow label="Implementation" value={ini.implementation_description} />
              <FieldRow label="Do owner" value={ini.do_owner} />
              <FieldRow label="Do status" value={ini.do_status} />
            </>
          )}
        </Section>
      )}

      {/* Check fields */}
      {stageIdx >= 2 && (
        <Section label="Check">
          {ini.check_sufficient_data ? (
            <CheckResults ini={ini} />
          ) : (
            <div className="al-check-pending">
              {ini.check_computed_at
                ? `Insufficient post-implementation data yet. Post n=${ini.check_post_n}.`
                : "Check metrics not yet computed. Run derive pipeline after implementation."}
            </div>
          )}
        </Section>
      )}

      {/* Act fields */}
      {stageIdx >= 3 && (
        <Section label="Act">
          {canEdit ? (
            <>
              <div className="al-form-group">
                <label>Decision</label>
                <select
                  value={updateForm.act_decision ?? ini.act_decision ?? ""}
                  onChange={(e) => u("act_decision", e.target.value)}
                >
                  {["", "standardize", "adjust", "abandon"].map((o) => (
                    <option key={o} value={o}>{o || "—"}</option>
                  ))}
                </select>
              </div>
              <EditField label="Act notes"
                value={updateForm.act_notes ?? ini.act_notes}
                onChange={(v) => u("act_notes", v)} multiline />
            </>
          ) : (
            <>
              <FieldRow label="Decision" value={ini.act_decision} />
              <FieldRow label="Act notes" value={ini.act_notes} />
            </>
          )}
        </Section>
      )}

      {/* Stage history */}
      {history?.length > 0 && (
        <Section label="Stage History">
          <div className="al-history">
            {history.map((h, i) => (
              <div key={i} className="al-history-item">
                <span>{h.from_stage} → {h.to_stage}</span>
                {h.notes && <span className="al-history-notes"> — {h.notes}</span>}
                <span className="al-history-date">{h.created_at?.slice(0, 16)}</span>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Actions */}
      {canEdit && (
        <div className="al-ini-actions">
          {stageIdx < STAGES.length - 1 && (
            <button className="al-btn-secondary" onClick={() => onAdvanceStage(stage)}>
              Advance to {STAGE_LABELS[STAGES[stageIdx + 1]]}
            </button>
          )}
          <div className="al-form-group al-inline">
            <label>Notes for this update</label>
            <input type="text"
              value={updateForm.notes || ""}
              onChange={(e) => u("notes", e.target.value)}
              placeholder="Optional notes"
            />
          </div>
          <button className="al-btn-primary" onClick={onSave} disabled={saving}>
            {saving ? "Saving…" : "Save Changes"}
          </button>
          {saveError && <div className="al-error">{saveError}</div>}
        </div>
      )}
    </div>
  );
}

function CheckResults({ ini }) {
  const cr = ini.check_results || {};
  const ur = cr.unresolved_rate;
  return (
    <div className="al-check-results">
      <div className="al-check-caveats">
        {ini.check_results?.caveats || "Indicative only — correlation, not causation."}
      </div>
      {ur && (
        <div className="al-check-metric">
          <div className="al-check-metric-name">Unresolved Rate</div>
          <div className="al-check-metric-row">
            <span>Baseline: {ur.baseline_value != null ? `${Math.round(ur.baseline_value * 100)}%` : "N/A"} (n={ur.n_baseline})</span>
            <span className="al-arrow">→</span>
            <span>Post: {ur.post_value != null ? `${Math.round(ur.post_value * 100)}%` : "N/A"} (n={ur.n_post})</span>
            <span className={`al-check-direction al-check-direction--${ur.direction}`}>
              {ur.direction === "improved" ? "Improved" : ur.direction === "worsened" ? "Worsened" : "No clear change"}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

function Section({ label, children }) {
  return (
    <div className="al-section">
      <h4 className="al-section-label">{label}</h4>
      {children}
    </div>
  );
}

function FieldRow({ label, value }) {
  if (!value) return null;
  return (
    <div className="al-field-row">
      <span className="al-field-label">{label}:</span>
      <span className="al-field-value">{value}</span>
    </div>
  );
}

function EditField({ label, value, onChange, multiline = false }) {
  return (
    <div className="al-form-group">
      <label>{label}</label>
      {multiline ? (
        <textarea rows={3} value={value || ""} onChange={(e) => onChange(e.target.value)} />
      ) : (
        <input type="text" value={value || ""} onChange={(e) => onChange(e.target.value)} />
      )}
    </div>
  );
}

function CreateInitiativeModal({ onClose, onCreated }) {
  const [form, setForm] = useState({
    title: "", problem_statement: "", root_cause_hypothesis: "",
    target_metric: "", target_change: "", owner: "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const u = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async () => {
    if (!form.title.trim()) { setError("Title is required"); return; }
    setSaving(true);
    setError("");
    try {
      await actionApi.createInitiative(form);
      onCreated();
    } catch (e) {
      const msg = e?.data?.detail;
      setError(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="al-modal-overlay" onClick={onClose}>
      <div className="al-modal al-modal--wide" onClick={(e) => e.stopPropagation()}>
        <h3>New PDCA Initiative</h3>
        {[
          { key: "title", label: "Title *" },
          { key: "owner", label: "Owner" },
          { key: "target_metric", label: "Target metric" },
          { key: "target_change", label: "Target change" },
        ].map(({ key, label }) => (
          <div className="al-form-group" key={key}>
            <label>{label}</label>
            <input type="text" value={form[key]} onChange={(e) => u(key, e.target.value)} />
          </div>
        ))}
        {["problem_statement", "root_cause_hypothesis"].map((key) => (
          <div className="al-form-group" key={key}>
            <label>{key.replace(/_/g, " ")}</label>
            <textarea rows={3} value={form[key]} onChange={(e) => u(key, e.target.value)} />
          </div>
        ))}
        {error && <div className="al-error">{error}</div>}
        <div className="al-modal-actions">
          <button className="al-btn-ghost" onClick={onClose}>Cancel</button>
          <button className="al-btn-primary" onClick={submit} disabled={saving}>
            {saving ? "Creating…" : "Create"}
          </button>
        </div>
      </div>
    </div>
  );
}
