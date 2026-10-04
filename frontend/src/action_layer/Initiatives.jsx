// frontend/src/action_layer/Initiatives.jsx
// PDCA Initiatives: list, create, and advance through Plan→Do→Check→Act stages.

import { useState, useEffect, useRef } from "react";
import { actionApi } from "./api.js";

const STAGES = ["plan", "do", "check", "act"];
const STAGE_LABELS = { plan: "Plan", do: "Do", check: "Check", act: "Act" };
const STAGE_COLORS = { plan: "#6366f1", do: "#0ea5e9", check: "#f59e0b", act: "#22c55e" };

const METRIC_OPTIONS = [
  { key: "unresolved_rate",       label: "Unresolved Rate",         unit: "ratio 0–1", hint: "e.g. 0.35 for 35%" },
  { key: "weekly_volume",         label: "Weekly Call Volume",       unit: "integer",   hint: "e.g. 50" },
  { key: "escalation_rate",       label: "Escalation Rate",          unit: "ratio 0–1", hint: "e.g. 0.10 for 10%" },
  { key: "false_resolution_rate", label: "False Resolution Rate",    unit: "ratio 0–1", hint: "e.g. 0.20 for 20%" },
  { key: "custom",                label: "Custom / Other",           unit: "numeric",   hint: "any numeric target" },
];


// Module-level helper — used by InitiativeDetail (no closure over React state)
function getAdvanceError(currentStage, form, ini) {
  if (!ini) return null;
  const metricKey = (form.metric_key != null ? form.metric_key : (ini.metric_key || ""));
  const targetVal = form.target_value != null ? form.target_value : ini.target_value;
  const implDesc  = (form.implementation_description != null ? form.implementation_description : (ini.implementation_description || ""));
  const implDate  = form.implementation_date != null ? form.implementation_date : ini.implementation_date;
  if (currentStage === "plan") {
    if (!metricKey) return "Select a metric before advancing.";
    if (targetVal === null || targetVal === undefined || targetVal === "") return "Enter a numeric target value before advancing.";
  }
  if (currentStage === "do") {
    if (!implDesc) return "Enter an implementation description before advancing.";
    if (!implDate) return "Enter an implementation date before advancing.";
  }
  return null;
}

export default function Initiatives({ currentUser, autoCreate = false, onAutoCreateDone }) {
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
  const [saveSuccess, setSaveSuccess] = useState(false);

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

  // Auto-open create modal once when navigated here from Recurring Issues.
  // Use a ref so it fires only on the initial mount, not on re-renders.
  const autoCreateHandled = useRef(false);
  useEffect(() => {
    if (autoCreate && !autoCreateHandled.current) {
      autoCreateHandled.current = true;
      setShowCreate(true);
      onAutoCreateDone?.();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
    setSaveSuccess(false);
    try {
      await actionApi.updateInitiative(selected.id, updateForm);
      await load();
      const d = await actionApi.getInitiative(selected.id);
      setDetail(d);
      setUpdateForm({});
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
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
                key={`${detail.initiative?.id}-${detail.initiative?.stage}-${detail.initiative?.iteration}`}
                ini={detail.initiative}
                history={detail.stage_history}
                canEdit={canEdit}
                updateForm={updateForm}
                setUpdateForm={setUpdateForm}
                onSave={saveUpdate}
                saving={saving}
                saveError={saveError}
                saveSuccess={saveSuccess}
                onAdvanceStage={advanceStage}
                getAdvanceError={getAdvanceError}
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

function InitiativeDetail({ ini, history, canEdit, updateForm, setUpdateForm, onSave, saving, saveError, saveSuccess, onAdvanceStage, getAdvanceError }) {
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

      {/* PDCA Stage progress + iteration */}
      <div className="al-pdca-progress-row">
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
        {ini.iteration > 1 && (
          <span className="al-iteration-badge">Iteration {ini.iteration}</span>
        )}
      </div>

      {/* Plan fields */}
      <Section label="Plan">
        {canEdit ? (
          <>
            <EditField label="Problem statement"
              value={updateForm.problem_statement ?? ini.problem_statement}
              onChange={(v) => u("problem_statement", v)} multiline
              hint="Suggested from evidence — edit as needed" />
            <EditField label="Root cause hypothesis"
              value={updateForm.root_cause_hypothesis ?? ini.root_cause_hypothesis}
              onChange={(v) => u("root_cause_hypothesis", v)} multiline
              hint="Suggested from evidence — edit as needed" />
            <div className="al-form-row">
              <div className="al-form-group">
                <label>Metric to track</label>
                <select
                  value={updateForm.metric_key ?? ini.metric_key ?? ""}
                  onChange={(e) => u("metric_key", e.target.value)}
                >
                  <option value="">— Select metric —</option>
                  {METRIC_OPTIONS.map((m) => (
                    <option key={m.key} value={m.key}>{m.label}</option>
                  ))}
                </select>
              </div>
              <div className="al-form-group">
                <label>
                  Target value
                  {(() => {
                    const mk = updateForm.metric_key ?? ini.metric_key;
                    const m = METRIC_OPTIONS.find((o) => o.key === mk);
                    return m ? <span className="al-field-hint"> ({m.hint})</span> : null;
                  })()}
                </label>
                <input
                  type="number"
                  step="0.01"
                  placeholder="e.g. 0.35"
                  value={updateForm.target_value ?? ini.target_value ?? ""}
                  onChange={(e) => u("target_value", e.target.value === "" ? null : parseFloat(e.target.value))}
                />
                {ini.baseline_metrics?.unresolved_rate?.baseline_value !== undefined && (
                  <span className="al-field-hint">
                    Baseline: {(ini.baseline_metrics.unresolved_rate.baseline_value * 100).toFixed(1)}%
                    (frozen at creation)
                  </span>
                )}
              </div>
            </div>
          </>
        ) : (
          <>
            <FieldRow label="Problem statement" value={ini.problem_statement} />
            <FieldRow label="Root cause hypothesis" value={ini.root_cause_hypothesis} />
            {ini.metric_key && (
              <FieldRow label="Metric"
                value={METRIC_OPTIONS.find((m) => m.key === ini.metric_key)?.label || ini.metric_key} />
            )}
            {ini.target_value !== null && ini.target_value !== undefined && (
              <FieldRow label="Target value" value={String(ini.target_value)} />
            )}
            {/* legacy */}
            {!ini.metric_key && <FieldRow label="Target metric" value={ini.target_metric} />}
            {!ini.metric_key && <FieldRow label="Target change" value={ini.target_change} />}
          </>
        )}
        {ini.baseline_metrics && Object.keys(ini.baseline_metrics).length > 0 && (
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
            <div className="al-form-group">
              <label>Implementation date</label>
              <input
                type="date"
                value={(updateForm.implementation_date ?? ini.implementation_date ?? "").slice(0, 10)}
                onChange={(e) => u("implementation_date", e.target.value ? e.target.value + "T00:00:00" : "")}
              />
            </div>
            <div className="al-form-row">
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
            </div>
            <div className="al-form-group">
              <label>Customers informed</label>
              <div className="al-radio-row">
                {[{v: null, l: "—"}, {v: true, l: "Yes"}, {v: false, l: "No"}].map(({v, l}) => (
                  <label key={l} className="al-radio-label">
                    <input type="radio"
                      checked={(updateForm.customers_informed ?? ini.customers_informed) === v}
                      onChange={() => u("customers_informed", v)}
                    /> {l}
                  </label>
                ))}
              </div>
            </div>
          </>
        ) : (
          <>
            <FieldRow label="Implementation" value={ini.implementation_description} />
            <FieldRow label="Date" value={ini.implementation_date?.slice(0, 10)} />
            <FieldRow label="Do owner" value={ini.do_owner} />
            <FieldRow label="Do status" value={ini.do_status} />
            <FieldRow label="Customers informed" value={ini.customers_informed === true ? "Yes" : ini.customers_informed === false ? "No" : null} />
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
              ? `Not enough post-fix data yet (n=${ini.check_post_n ?? 0}, minimum required: 10 conversations over 7 days). Check again after more conversations are processed.`
              : "Check metrics not yet computed. Run the derive pipeline after the implementation date has passed."}
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
                {(updateForm.act_decision ?? ini.act_decision) === "adjust" && (
                  <div className="al-act-adjust-note">
                    Adjust will start a new iteration (Iteration {(ini.iteration || 1) + 1}),
                    resetting Do/Check/Act fields and returning to Plan.
                    The frozen baseline is preserved.
                  </div>
                )}
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
      {canEdit && (() => {
        const advErr = getAdvanceError(stage, updateForm, ini);
        const nextStage = STAGES[stageIdx + 1];
        return (
          <div className="al-ini-actions">
            {stageIdx < STAGES.length - 1 && (
              <div className="al-advance-group">
                <button
                  className="al-btn-secondary"
                  onClick={() => {
                    if (!advErr) onAdvanceStage(stage);
                  }}
                  disabled={!!advErr}
                  title={advErr || undefined}
                >
                  Advance to {STAGE_LABELS[nextStage]}
                </button>
                {advErr && <div className="al-advance-error">{advErr}</div>}
              </div>
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
            {saveSuccess && (
              <div className="al-save-success">Changes saved</div>
            )}
            {saveError && <div className="al-error">{saveError}</div>}
          </div>
        );
      })()}
    </div>
  );
}

function CheckResults({ ini }) {
  const cr = ini.check_results || {};
  const metricKey = ini.metric_key || "unresolved_rate";
  const metricLabel = METRIC_OPTIONS.find((m) => m.key === metricKey)?.label || metricKey;
  // check_results is a dict keyed by metric slug
  const rows = Object.entries(cr).filter(([k]) => k !== "caveats").map(([k, v]) => ({
    metric: METRIC_OPTIONS.find((m) => m.key === k)?.label || k,
    baseline: v.baseline_value,
    post: v.post_value,
    n_baseline: v.n_baseline,
    n_post: v.n_post,
    direction: v.direction,
    change_pct: v.change_pct,
  }));

  const fmtVal = (v, key) => {
    if (v === null || v === undefined) return "N/A";
    if (key?.includes("rate")) return `${(v * 100).toFixed(1)}%`;
    return Number.isInteger(v) ? String(v) : v.toFixed(2);
  };

  const dirClass = (d) => d === "improved" ? "al-chg--good" : d === "worsened" ? "al-chg--bad" : "al-chg--neutral";
  const dirLabel = (d) => d === "improved" ? "Improved" : d === "worsened" ? "Worsened" : "No clear change";

  return (
    <div className="al-check-results">
      <div className="al-check-caveat">
        Indicative only — correlation, not causation. Statistical significance not guaranteed.
      </div>
      {rows.length === 0 ? (
        <div className="al-check-pending">Check computed but no metric rows returned.</div>
      ) : (
        <table className="al-check-table">
          <thead>
            <tr>
              <th>Metric</th>
              <th>Before (n={rows[0]?.n_baseline ?? "?"})</th>
              <th>After (n={rows[0]?.n_post ?? "?"})</th>
              <th>Change</th>
              <th>Direction</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                <td>{r.metric}</td>
                <td>{fmtVal(r.baseline, r.metric)}</td>
                <td>{fmtVal(r.post, r.metric)}</td>
                <td>{r.change_pct !== null && r.change_pct !== undefined ? `${r.change_pct > 0 ? "+" : ""}${r.change_pct.toFixed(1)}%` : "N/A"}</td>
                <td><span className={`al-chg ${dirClass(r.direction)}`}>{dirLabel(r.direction)}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {ini.check_post_window_start && (
        <div className="al-check-window">
          Post window: {ini.check_post_window_start?.slice(0, 10)} – {ini.check_post_window_end?.slice(0, 10)}
          {" "}· n={ini.check_post_n}
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

function EditField({ label, value, onChange, multiline = false, hint }) {
  return (
    <div className="al-form-group">
      <label>{label}{hint && <span className="al-field-hint"> — {hint}</span>}</label>
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
    metric_key: "", target_value: "", owner: "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const u = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async () => {
    if (!form.title.trim()) { setError("Title is required"); return; }
    setSaving(true);
    setError("");
    const payload = {
      ...form,
      target_value: form.target_value !== "" ? parseFloat(form.target_value) : null,
    };
    try {
      await actionApi.createInitiative(payload);
      onCreated();
    } catch (e) {
      const msg = e?.data?.detail;
      setError(
        typeof msg === "string" ? msg
        : msg ? JSON.stringify(msg)
        : e?.message || "Failed to create initiative."
      );
    } finally {
      setSaving(false);
    }
  };

  const selectedMetric = METRIC_OPTIONS.find((m) => m.key === form.metric_key);

  return (
    <div className="al-modal-overlay" onClick={onClose}>
      <div className="al-modal al-modal--wide" onClick={(e) => e.stopPropagation()}>
        <h3>New PDCA Initiative</h3>
        <div className="al-form-group">
          <label>Title *</label>
          <input type="text" value={form.title} onChange={(e) => u("title", e.target.value)} />
        </div>
        <div className="al-form-group">
          <label>Owner</label>
          <input type="text" value={form.owner} onChange={(e) => u("owner", e.target.value)} />
        </div>
        {["problem_statement", "root_cause_hypothesis"].map((key) => (
          <div className="al-form-group" key={key}>
            <label>
              {key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
              <span className="al-field-hint"> — Suggested from evidence, editable</span>
            </label>
            <textarea rows={3} value={form[key]} onChange={(e) => u(key, e.target.value)} />
          </div>
        ))}
        <div className="al-form-row">
          <div className="al-form-group">
            <label>Metric to track</label>
            <select value={form.metric_key} onChange={(e) => u("metric_key", e.target.value)}>
              <option value="">— Select metric —</option>
              {METRIC_OPTIONS.map((m) => (
                <option key={m.key} value={m.key}>{m.label}</option>
              ))}
            </select>
          </div>
          <div className="al-form-group">
            <label>Target value
              {selectedMetric && <span className="al-field-hint"> ({selectedMetric.hint})</span>}
            </label>
            <input
              type="number"
              step="0.01"
              placeholder={selectedMetric?.hint || "numeric"}
              value={form.target_value}
              onChange={(e) => u("target_value", e.target.value)}
            />
          </div>
        </div>
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
