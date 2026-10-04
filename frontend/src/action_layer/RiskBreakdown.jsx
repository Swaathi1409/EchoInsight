// frontend/src/action_layer/RiskBreakdown.jsx
// Expandable risk component breakdown table.

export default function RiskBreakdown({ components }) {
  if (!components || components.length === 0) return null;

  const triggered = components.filter((c) => c.triggered);
  const notTriggered = components.filter((c) => !c.triggered);

  return (
    <div className="al-risk-breakdown">
      <h3>Risk Breakdown</h3>
      <p className="al-risk-breakdown-note">
        Example policy — owner review required. Each signal references a stored data field.
      </p>
      <table className="al-table">
        <thead>
          <tr>
            <th>Signal</th>
            <th>Points</th>
            <th>Evidence</th>
          </tr>
        </thead>
        <tbody>
          {triggered.map((c) => (
            <tr key={c.name} className="al-table-row--triggered">
              <td>
                <div className="al-table-name">{c.name.replace(/_/g, " ")}</div>
                <div className="al-table-rule">{c.rule}</div>
              </td>
              <td className="al-table-points al-table-points--active">+{c.points}</td>
              <td>
                <EvidenceRef ev={c.evidence_ref} />
                {c.description && <div className="al-table-desc">{c.description}</div>}
              </td>
            </tr>
          ))}
          {notTriggered.map((c) => (
            <tr key={c.name} className="al-table-row--not-triggered">
              <td>
                <div className="al-table-name al-table-name--dim">{c.name.replace(/_/g, " ")}</div>
              </td>
              <td className="al-table-points al-table-points--dim">+{c.points}</td>
              <td className="al-table-not-triggered">not triggered</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function EvidenceRef({ ev }) {
  if (!ev || Object.keys(ev).length === 0) return <span className="al-ev-empty">—</span>;
  const parts = [];
  if (ev.type) parts.push(`type: ${ev.type}`);
  if (ev.quote) parts.push(`"${ev.quote.slice(0, 80)}"`);
  if (ev.value) parts.push(`value: ${ev.value}`);
  if (ev.field) parts.push(`field: ${ev.field}`);
  if (ev.count !== undefined) parts.push(`count: ${ev.count}`);
  if (ev.commitment_id) parts.push(`commitment: ${ev.commitment_id.slice(0, 8)}…`);
  return <span className="al-ev-ref">{parts.join(" · ")}</span>;
}
