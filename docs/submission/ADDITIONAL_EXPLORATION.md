# Additional Exploration

This document catalogues explorations conducted beyond the baseline assignment requirements.

## 1. Selective Verification (Second Opinion)
**Question**: How can we reduce false positives on high-risk QA items without doubling inference costs on every turn?
**Method**: Implemented a routing mechanism (`backend/qa/verification.py`) that sends only specific items (critical items, low-confidence scores, absence-based evidence) to a secondary LLM for verification.
**Result**: Code path is active and successfully applies `human_review_required` on verdict mismatch. 
**Decision Taken**: Shipped in production. Documented in `ADR-002` and Diagram `D7`.

## 2. Deterministic Phrase Matching
**Question**: Are embeddings strictly necessary for detecting standard telecom greetings and disclosures?
**Method**: Tested a deterministic regex matcher (`backend/qa/phrase_matcher.py`) against 4 standard checklist items. 
**Result**: Regex achieved near-perfect recall on rigid scripts with zero compute cost.
**Decision Taken**: Made regex the default. Embeddings placed behind an `EMBEDDINGS_ENABLED=false` feature flag (`ADR-006`).

## 3. Ephemeral File System Workarounds
**Question**: Render free-tier Docker containers have ephemeral file systems. How do we ensure the demo dataset (`demo_seed.db`) works on PostgreSQL without manually restoring it every time the server wakes up?
**Method**: Implemented a boot-time check (`backend/api/main.py:79-111`) that detects missing data and idempotently runs the `seed_demonstration()` script if the `SEED_DEMO_DATA=true` environment variable is set.
**Result**: Seamless cold starts with full demo data on free-tier PostgreSQL.
**Decision Taken**: Deployed to Render. Documented in Diagram `D11`.

## 4. LLM Provider Redundancy
**Question**: What happens when the primary LLM provider (Groq) rate limits the app?
**Method**: Abstracted the client (`backend/llm/client.py`) to support OpenAI-compatible endpoints, allowing fallback to OpenRouter.
**Result**: Added `OPENROUTER_API_KEY` configuration. If set, it takes priority over Groq.
**Decision Taken**: Documented in `ADR-002` and `architecture_facts.json`.

## Not Run (Planned but skipped)
- **Dataset Profiling**: Did not profile the entire `talkmap/telecom-conversation-corpus` huggingface dataset due to licensing constraints regarding the redistribution of raw rows (`ADR-001`).
- **Text-to-SQL Analytics**: Considered using LLMs for the analytics dashboard but rejected it in favor of deterministic SQLAlchemy queries for speed and safety.
