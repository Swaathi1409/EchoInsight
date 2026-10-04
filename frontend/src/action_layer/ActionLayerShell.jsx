// frontend/src/action_layer/ActionLayerShell.jsx
// Master shell: checks if action layer is enabled, shows a branded disabled state,
// or renders the tabbed Action Intelligence dashboard.

import { useState, useEffect, useCallback } from "react";
import { actionApi } from "./api.js";
import RecoveryDesk from "./RecoveryDesk.jsx";
import RecurringIssues from "./RecurringIssues.jsx";
import Initiatives from "./Initiatives.jsx";
import AgentInsights from "./AgentInsights.jsx";

const TABS = [
  { id: "recovery", label: "Recovery Desk" },
  { id: "issues", label: "Recurring Issues" },
  { id: "initiatives", label: "PDCA Initiatives" },
  { id: "agents", label: "Agent Insights" },
];

export default function ActionLayerShell({ currentUser }) {
  const [status, setStatus] = useState(null);
  const [seeding, setSeeding] = useState(false);
  const [seedMsg, setSeedMsg] = useState("");
  const [activeTab, setActiveTab] = useState("recovery");
  const [autoCreate, setAutoCreate] = useState(false);

  // Called from RecurringIssues when user clicks "Create PDCA Initiative"
  const handleCreateInitiative = useCallback(() => {
    setActiveTab("initiatives");
    setAutoCreate(true);
  }, []);

  const checkStatus = useCallback(async () => {
    try {
      const s = await actionApi.status();
      setStatus(s);
    } catch {
      setStatus({ enabled: false });
    }
  }, []);

  useEffect(() => { checkStatus(); }, [checkStatus]);

  const handleSeedDemo = async () => {
    setSeeding(true);
    setSeedMsg("");
    try {
      const res = await actionApi.seedDemo();
      setSeedMsg(res.steps?.join(" · ") || "Done");
      await checkStatus();
    } catch (e) {
      setSeedMsg(`Error: ${e?.data?.detail || "Failed"}`);
    } finally {
      setSeeding(false);
    }
  };

  if (!status) {
    return (
      <div className="al-loading">
        <div className="al-spinner" />
        <span>Checking Action Intelligence Layer&hellip;</span>
      </div>
    );
  }

  if (!status.enabled) {
    return (
      <div className="al-disabled-shell">
        <div className="al-disabled-card">
          <div className="al-disabled-icon">&#9889;</div>
          <h2>Action Intelligence Layer</h2>
          <p className="al-disabled-sub">
            This layer is currently disabled. An administrator must enable it
            and run the derive pipeline before data is available.
          </p>
          {currentUser?.role === "admin" && (
            <div className="al-disabled-actions">
              <button
                className="al-btn-primary"
                onClick={handleSeedDemo}
                disabled={seeding}
              >
                {seeding ? "Seeding…" : "Enable and Seed Demo Data"}
              </button>
              {seedMsg && <p className="al-seed-msg">{seedMsg}</p>}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="al-shell">
      <div className="al-shell-header">
        <div className="al-shell-title">
          <span className="al-badge">Action Intelligence</span>
          <h1>Action Intelligence Layer</h1>
          <p className="al-shell-sub">
            Priorities and actions derived from stored analysis — no fabrication.
          </p>
        </div>
        {currentUser?.role === "admin" && (
          <div className="al-shell-actions">
            <button
              className="al-btn-secondary"
              onClick={handleSeedDemo}
              disabled={seeding}
            >
              {seeding ? "Running…" : "Re-derive All"}
            </button>
            {seedMsg && <span className="al-seed-inline">{seedMsg}</span>}
          </div>
        )}
      </div>

      <div className="al-tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={`al-tab${activeTab === t.id ? " al-tab--active" : ""}`}
            onClick={() => setActiveTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="al-tab-content">
        {activeTab === "recovery" && <RecoveryDesk currentUser={currentUser} />}
        {activeTab === "issues" && <RecurringIssues currentUser={currentUser} onCreateInitiative={handleCreateInitiative} />}
        {activeTab === "initiatives" && <Initiatives currentUser={currentUser} autoCreate={autoCreate} onAutoCreateDone={() => setAutoCreate(false)} />}
        {activeTab === "agents" && <AgentInsights currentUser={currentUser} />}
      </div>
    </div>
  );
}
