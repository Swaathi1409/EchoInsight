# Dataset Documentation

## Source

**Name**: telecom-200k (talkmap/telecom-conversation-corpus)
**URL**: https://huggingface.co/datasets/talkmap/telecom-conversation-corpus
**Revision pinned**: `c8bfc7797a347b493f65fdc4e4c9694a8a19b56f`
**Last modified**: 2024-03-15
**License**: MIT (stated in dataset card)
**Language**: English

## Description

200,000 synthetically generated customer service conversations for the telecom industry. Two speakers per conversation: a customer and an agent. The fictional company name "Union Mobile" appears throughout. This dataset is **not real customer data** and must never be described as such.

The generating LLM is not identified in the dataset card. Redistribution of raw rows is avoided out of caution (see ADR-001).

## Files

| File | Rows (approx.) | Size |
|------|---------------|------|
| `telecom_200k.csv` | 2,390,000 | 714 MB |
| `telecom_corpus_supplimental.csv` | 1,336,699 | 23 MB |
| **Total (single train split)** | **3,726,699** | **738 MB** |

## Schema

| Column | Type | Description |
|--------|------|-------------|
| `conversation_id` | string | 32-character hex UUID identifying the conversation |
| `speaker` | string | `agent` or `client` (mapped to `customer` in our domain model) |
| `date_time` | string | ISO 8601 timestamp, usually with microseconds |
| `text` | string | Turn text, variable length |

## Profiling Summary (Bounded - 500 rows, 5 offsets)

Profiling was run on 2026-10-02 using the HuggingFace datasets-server API. Full corpus was not downloaded. Statistics may not represent the full distribution.

| Metric | Value | Notes |
|--------|-------|-------|
| Total rows | 3,726,699 | From /info endpoint |
| Estimated conversations | ~200,000 | 3,726,699 / ~18.6 avg turns |
| Speaker ratio | agent 52%, client 48% | n=500 |
| Empty text rows | 0 | n=500 |
| Text length (median) | 108 chars | n=500 |
| Text length (p90) | 258 chars | n=500 |
| Text length (max observed) | 542 chars | n=500 |
| Avg turns per conversation | ~16.4 | n=25 complete conversations |
| Median turns per conversation | 15 | n=25 |
| Max turns observed | 23 | n=25 |
| Timestamps with microseconds | 89.8% | n=500 |
| Customer-first conversations | ~18% | n=33 partial conversations |
| Rows with PIN/account patterns | 6.2% | n=500; synthetic but treated as sensitive |
| Rows with masked patterns (#X+) | 0.4% | n=500 |
| Rows with noise markers ((pause)) | 0.6% | n=500 |
| Duplicate (conv_id, text) pairs | 10/500 | 2%; deduplication required |
| Rows with closing phrases | 15.6% | n=500 |
| Rows with verification phrases | 7.4% | n=500 |

**Ordering**: Statistics are consistent across 5 evenly spaced offsets. No ordering bias detected. Conversations appear contiguous within the file (turns for one conversation are sequential). Conversations themselves are randomly ordered across the file.

## Observed Data Characteristics

- **Fictional brand**: "Union Mobile" appears consistently.
- **Identity verification**: Agent asks customer to verify with PIN (e.g., "my account PIN is 1234") or account number (e.g., "#XXXXX"). These appear synthetic but are treated as sensitive.
- **Noise**: `(pause)` markers appear; garbled or truncated words appear (e.g., "Thank, thank you", "it's possible that"); last turn in some conversations is truncated.
- **Consecutive same-speaker turns**: Not observed in sample but possible.
- **Abrupt endings**: Some conversations end with a truncated agent turn (e.g., "Thank you again "), suggesting dropped call simulation.
- **Generation artifacts**: Sentences that appear mid-thought, dropped words.

## What Is Missing (Must Be Created)

| Missing item | How handled |
|-------------|-------------|
| Agent/team IDs | Synthetic assignment from hash(conversation_id) to 25 agents, 5 teams |
| Intent labels | Produced by LLM extraction |
| Sentiment labels | Produced by LLM extraction |
| Resolution labels | Produced by LLM extraction |
| QA labels | Produced by QA engine |
| Churn labels | Not available; heuristic signal-based risk level only |
| Gold annotations | Owner task; workbook at evals/gold_annotation_workbook.csv |

## Taxonomy Areas (Observed)

Thin taxonomy areas requiring labeled fixtures (since corpus may not have sufficient examples):
- Roaming or international calls
- SIM activation or replacement
- Device issues (hardware)
- Technical visit scheduling
- Cancellation or churn intent (requires careful QA)

## License Notes

The dataset card states MIT. The following caveats apply:
- The generating LLM is not identified. MIT on generated content may not override the generating model's terms.
- **Decision**: Raw rows are not committed to this repository. Only manifests (conversation ID lists) are committed. A fetch script reconstructs local samples.
- The owner should review the current Groq terms (docs/security.md) before sending any transcript content to the Groq API.

## Analysis Pool

See `data/manifests/analysis_pool_v1.json`:
- 147 conversations, seed=42, revision c8bfc77
- Stratified by turn-count bucket and edge cases
- 36 conversations designated as gold set (13 dev, 23 test)
- Test IDs must never appear in prompts, fixtures, or tuning files

To fetch a conversation from the pool:
```python
from data.scripts.fetch_conversations import fetch_conversation
turns = fetch_conversation(conversation_id)
```
