# Phase 0 Audit: Checklist and Cases

## 1. Baseline
- Baseline exact row counts and API latency snapshots are captured in `proceedings.md` and `.backup/golden_snapshots.json`.

## 2. QA Scoring Definition Today
- **Files**: Definitions are read directly from `backend/config/policy_example_v1.yaml`.
- **Tables**: There are no `qa_checklist` tables in the database schema.
- **Functions**: `backend/api/admin.py` reads yaml for `/api/v1/checklists`. The QA worker logic reads the policy yaml via `POLICY_VERSION = "example_v1"`.
- **Why example_v1 shows 0 items**: The UI parses `.items`, but the YAML provides `.checklist_items`. The `.active` flag is missing from the YAML.
- **Worker vs API**: Both currently read from the same source (`backend/config/`).
- **Analyses storage**: The tables `analyses` and `qa_results` store `policy_version` and `checklist_version` containing the string `"example_v1"`.

## 3. Inventory
- **Checklist endpoints**: `GET /api/v1/checklists`, `POST /api/v1/checklists`, `GET /api/v1/checklists/{version}`, `PATCH /api/v1/checklists/{version}` (all mock implementations in `backend/api/admin.py` backed by YAML).
- **Case tables**: `cases`, `case_conversations`.
- **Columns**: `case_id`, `external_id`, `title`, `status`, `created_by`, `created_at`, `updated_at`, `notes`.
- **Missing columns**: `data_source` (to be added to cases), `qa_checklist` family of tables (to be added).

## 4. Configuration Packaging
- Config files are placed under `backend/config/` and are copied directly into the Docker image since no `.dockerignore` excludes them.

## 5. Data Source Mapping (Test Artifacts)
Existing cases:
- "Customer Emma Wilson  Billing & Network Issues" -> **fixture**
- "E2E Test Case" -> **test_artifact**
- "Debug Case" -> **test_artifact**

All other conversations are assumed to be from the default **dataset_pool** unless they have similar titles.
