# EchoInsight Evaluation Rubric

This rubric is used for human annotation of the gold conversation set.
All LLM pre-filled values are marked `pre_annotation_needs_human_review`.
Results are labeled **provisional** until a human reviewer confirms each item.

## How to Use

1. Open `evals/gold_workbook.csv` in a spreadsheet tool.
2. For each row, the gold conversation ID, turn IDs, and LLM pre-filled values are shown.
3. Review each pre-filled value against the conversation transcript.
4. Change `review_status` from `pre_annotation_needs_human_review` to `confirmed` or `corrected`.
5. If correcting, update the value and add a note in the `reviewer_notes` column.
6. Save the CSV and run `make eval` to compute metrics.

**Critical rule**: Never change a test-split conversation ID's annotations based on model output patterns. Annotate from the transcript only.

---

## Field Definitions

### Summary
- **factual**: Does the summary assert only facts supported by the transcript? (yes / no)
- **complete**: Does it cover the main reason, resolution, and key events? (yes / no)
- **unsupported_claim**: Does it assert an outcome not evidenced in the transcript? (yes / no)

### Call Reasons (multi-label)

Label each conversation with all applicable call reasons from the taxonomy:

| Label | Definition |
|-------|-----------|
| `network_coverage_or_dropped_calls` | Customer reports dropped calls, poor signal, or dead zones |
| `mobile_data_issue` | Mobile data not working, slow, or intermittent |
| `internet_or_broadband_outage` | Home internet or broadband not working |
| `billing_dispute` | Incorrect charges, unexpected fees, billing errors |
| `plan_change_or_upgrade` | Customer wants to change, upgrade, or downgrade their plan |
| `cancellation_or_churn_intent` | Customer mentions cancelling or threatening to leave |
| `roaming_or_international` | Issues or questions about roaming or international calls |
| `sim_or_activation` | SIM card issues, new SIM, or service activation |
| `device_issue` | Phone hardware or software problems |
| `technical_visit` | Scheduling or following up on a technician visit |
| `account_access_or_security` | Login issues, PIN reset, account security |
| `complaint_or_escalation` | Customer explicitly escalates or lodges a formal complaint |
| `general_inquiry` | Information request not fitting other categories |

### Sentiment (per turn)

| Value | Definition |
|-------|-----------|
| `positive` | Customer is happy, grateful, or satisfied |
| `neutral` | Customer is calm, factual, or ambiguous |
| `frustrated` | Customer is noticeably annoyed or impatient |
| `angry` | Customer is hostile, shouting, or threatening |

### Resolution

| Value | Definition |
|-------|-----------|
| `resolved` | Issue fully addressed; customer confirmed satisfied or problem confirmed fixed |
| `partially_resolved` | Some aspects addressed but issue not fully closed |
| `pending` | Action promised but not yet completed |
| `unresolved` | Issue remains open with no clear path to resolution |
| `escalated` | Call transferred to a specialist or higher level |
| `unknown` | Cannot determine from the transcript |

**False resolution**: Mark `true` if the agent said "resolved" or closed the call but:
- A commitment remains open or unconfirmed, OR
- The customer expressed continued dissatisfaction at the end, OR
- The stated resolution is not supported by the transcript.

### Follow-up Actions

For each committed action, annotate:
- `description`: What was promised
- `owner`: Agent or customer (if specified)
- `deadline`: Date or timeframe (if mentioned; note if relative without timezone)
- `status_at_end`: `proposed`, `accepted`, `scheduled`, `completed`, `cancelled`, `uncertain`
- `evidence_turns`: Which turn IDs contain the commitment

### QA Checklist Items

| Item | Pass condition | Fail condition | Not applicable |
|------|--------------|----------------|---------------|
| `greeting` | Agent greeted within first 2 turns with name and company | No greeting in first 2 turns | Customer started the call and agent responded to an urgent issue immediately |
| `identity_verification` | Agent verified customer identity before accessing account | No verification before account access | No account action taken |
| `empathy` | Agent acknowledged customer's frustration or difficulty at least once | No acknowledgment of customer difficulty when clearly frustrated | Customer was neutral throughout |
| `disclosure` | Agent disclosed any applicable fees or limitations upfront | Agent recommended action without disclosing associated cost | No fee-bearing action taken |
| `prohibited_promises` | No guarantees of outcomes agent cannot control | Agent guaranteed specific outcome (refund, fix date) without authority | No outcome-sensitive statements |
| `closure` | Agent confirmed next steps and thanked customer | Call ended abruptly or without summary | Very short call (less than 3 turns) |

**Evidence**: Quote the exact turn text that supports the QA item result. The quote must be a substring of the stored redacted text.

### Confidence in Annotation

Rate your confidence in the annotation: `high`, `medium`, `low`.

Low confidence = the call is ambiguous and the item should be routed to `needs_review`.

---

## Annotation Split Rules

- **Development set (15 conversations)**: Used for prompt tuning, threshold calibration, and debugging.
- **Test set (25 conversations)**: Used ONLY for final metric reporting. Never used for tuning.
- An automated check (`tests/unit/test_leakage.py`) confirms no test ID appears in prompt files.

## Limitations

- LLM pre-annotation is provided only to speed up the process. All values must be human-verified.
- The gold set is small (40 conversations). Uncertainty in F1 scores will be high; always report counts alongside percentages.
- The dataset is fully synthetic. Annotation patterns may not generalize to real calls.
