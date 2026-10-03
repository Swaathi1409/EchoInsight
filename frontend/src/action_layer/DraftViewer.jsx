// frontend/src/action_layer/DraftViewer.jsx
// Displays the deterministic follow-up draft with gate status and placeholder highlights.

export default function DraftViewer({ draft }) {
  if (!draft) {
    return <div className="al-loading-inline">Loading draft…</div>;
  }
  if (draft.error) {
    return <div className="al-error">{draft.error}</div>;
  }

  const gateOk = draft.gate_status === "passed";

  return (
    <div className="al-draft">
      <div className="al-draft-header">
        <h3>Follow-up Draft</h3>
        <div className={`al-gate-badge al-gate-badge--${gateOk ? "ok" : "warn"}`}>
          {gateOk ? "Gate: Passed" : `Gate: ${draft.gate_status}`}
        </div>
      </div>

      <div className="al-draft-banner">{draft.banner}</div>
      <div className="al-draft-label">{draft.label}</div>

      <pre className="al-draft-content">
        <HighlightedDraft content={draft.content} placeholders={draft.placeholders || []} />
      </pre>

      {draft.placeholders?.length > 0 && (
        <div className="al-draft-placeholders">
          <h4>Placeholders requiring supervisor completion:</h4>
          <ul>
            {draft.placeholders.map((p, i) => <li key={i}>{p}</li>)}
          </ul>
        </div>
      )}

      {draft.facts_used?.length > 0 && (
        <details className="al-draft-facts">
          <summary>Facts used ({draft.facts_used.length})</summary>
          <ul>
            {draft.facts_used.map((f, i) => <li key={i}>{f}</li>)}
          </ul>
        </details>
      )}
    </div>
  );
}

function HighlightedDraft({ content, placeholders }) {
  if (!placeholders?.length) return <>{content}</>;

  // Highlight [PLACEHOLDER] text in the draft
  let result = content;
  const parts = content.split(/(\[[^\]]+\])/g);
  return (
    <>
      {parts.map((part, i) =>
        part.startsWith("[") && part.endsWith("]") ? (
          <span key={i} className="al-draft-placeholder-highlight">{part}</span>
        ) : (
          <span key={i}>{part}</span>
        )
      )}
    </>
  );
}
