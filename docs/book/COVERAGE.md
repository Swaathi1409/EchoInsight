# docs/book/COVERAGE.md
# EchoInsight Documentation Coverage Report
# Generated: 2026-10-06

## Volume Completeness

| Volume | File | Chapters | Key topics covered |
|--------|------|----------|-------------------|
| Vol 1 | EchoInsight_Vol1_Project_Documentation.docx | 9 Parts + Appendices | Problem, architecture, features, data, intelligence layer, product surfaces, security, decisions, roadmap |
| Vol 2 | EchoInsight_Vol2_Code_Walkthrough.docx | 4 Chapters | File cards (40+ files), feature traces, algorithm deep dives |
| Vol 3 | EchoInsight_Vol3_Setup_Run_and_Deployment_Guide.docx | 3 Parts | Local setup, Docker, Render + Vercel deployment, operations |
| Vol 4 | EchoInsight_Vol4_Viva_and_Defense_Handbook.docx | 5 Sections | 200+ Q&A, decision quick ref, demo scripts, numbers, inferred items |

## Inventory Coverage

All inventory items appear in at least one volume. Cross-reference:
- Every backend module: covered in Vol 2 Chapter 2 (File Cards) and Vol 1 Part 4-6
- Every frontend component: covered in Vol 1 Part 7 and Vol 2 Chapter 2
- Every test file: covered in Vol 1 Part 8 and Vol 2 Chapter 3
- Every ADR: covered in Vol 1 Part 9 and Vol 4 Section 2
- Every environment variable: covered in Vol 1 Appendix A and Vol 3 Part B

## Known Gaps

1. Frontend file cards in Vol 2 are abbreviated (key components described but not all hooks/props detailed)
2. Action Layer and Assistant file cards in Vol 2 are summarised at module level (16 + 10 modules)
3. Gold annotations not available — F1 metrics cannot be reported
4. Live screenshots not embedded (docs/screenshots/ directory is empty in current snapshot)
5. Mermaid diagrams rendered as text descriptions (no mermaid-cli available in build environment)

## Verification Status

- Code excerpts: all excerpts verified as present in referenced files at referenced lines
- Metrics: all numbers cited with source references; provisional/estimated clearly marked
- No placeholder text ("TODO", "TBD", "lorem") in any volume
- Bug report: all 23 bugs documented; none claimed as fixed (honest status: Open)

## How to Regenerate

    python scripts/generate_all_docs.py

Requires: python-docx (pip install python-docx)
Output: docs/EchoInsight_Vol1_*.docx through docs/EchoInsight_Vol4_*.docx
