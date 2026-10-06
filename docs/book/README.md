# docs/book/README.md
# EchoInsight Documentation Books

## Volumes

| Volume | File | Purpose |
|--------|------|---------|
| Vol 1 | docs/EchoInsight_Vol1_Project_Documentation.docx | Problem, architecture, decisions, limits, future scope (~100-150 pages) |
| Vol 2 | docs/EchoInsight_Vol2_Code_Walkthrough.docx | Every file explained, feature traces, algorithm deep dives |
| Vol 3 | docs/EchoInsight_Vol3_Setup_Run_and_Deployment_Guide.docx | Local setup, Docker, Render + Vercel deploy, operations |
| Vol 4 | docs/EchoInsight_Vol4_Viva_and_Defense_Handbook.docx | 200+ Q&A, demo scripts, decision quick ref, numbers |

## How to Regenerate

Run from the EchoInsight repository root:

    pip install python-docx
    python scripts/generate_all_docs.py

## Markdown Sources

- docs/book/00_inventory.md — full file inventory
- docs/book/COVERAGE.md — coverage report
- docs/book/README.md — this file

## Notes

- Do not run regeneration while the source code is being modified.
- All numbers and metrics are sourced from the project; see COVERAGE.md for verification status.
- The documents are generated from code; if code changes, regenerate.
