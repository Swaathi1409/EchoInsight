"""
EchoInsight Architecture Diagram Generator
Generates SVG/PNG diagrams for D0–D15 using matplotlib.
Run: python scripts/generate_architecture.py
All facts are loaded from docs/architecture/architecture_facts.json
"""
from __future__ import annotations
import json
import math
import os
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import matplotlib.patheffects as pe
from matplotlib.lines import Line2D

ROOT = Path(__file__).parent.parent
FACTS_PATH = ROOT / "docs" / "architecture" / "architecture_facts.json"
OUT_DIR = ROOT / "docs" / "architecture" / "diagrams"
OUT_DIR.mkdir(parents=True, exist_ok=True)

with open(FACTS_PATH, "r", encoding="utf-8") as f:
    FACTS = json.load(f)

# ── Colorblind-safe palette (Okabe-Ito + extensions) ──────────────────────────
C = {
    "service":      "#2E75B6",   # blue
    "llm":          "#E07B39",   # orange
    "store":        "#5A8A50",   # green
    "gate":         "#C0392B",   # red
    "external":     "#7D7D7D",   # grey
    "optional":     "#B0B0D0",   # light purple/grey
    "user":         "#D4AC0D",   # gold
    "deterministic":"#2E75B6",
    "band_trust":   "#EBF5FB",
    "band_obs":     "#EBF7EE",
    "band_dep":     "#FEF9E7",
    "bg":           "#FAFAFA",
    "text_dark":    "#1A1A1A",
    "text_light":   "#FFFFFF",
    "arrow":        "#2C3E50",
    "arrow_opt":    "#808080",
    "border":       "#404040",
}

TITLE_FONT = {"fontsize": 11, "fontweight": "bold", "color": C["text_dark"]}
LABEL_FONT = {"fontsize": 8.5, "color": C["text_dark"]}
SMALL_FONT = {"fontsize": 7.5, "color": "#444"}


def _save(fig, name: str, dpi: int = 150):
    svg_path = OUT_DIR / f"{name}.svg"
    png_path = OUT_DIR / f"{name}.png"
    fig.savefig(str(svg_path), format="svg", bbox_inches="tight", facecolor=fig.get_facecolor())
    fig.savefig(str(png_path), format="png", dpi=dpi, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  Saved {name}.svg  {name}.png")


def _box(ax, x, y, w, h, label, sub="", color=C["service"], text_color=C["text_light"],
         alpha=1.0, style="round,pad=0.05", linestyle="-", lw=1.5):
    box = FancyBboxPatch((x - w/2, y - h/2), w, h,
                         boxstyle=style, linewidth=lw,
                         edgecolor=C["border"], facecolor=color, alpha=alpha,
                         linestyle=linestyle)
    ax.add_patch(box)
    if sub:
        ax.text(x, y + 0.08, label, ha="center", va="center",
                fontsize=9, fontweight="bold", color=text_color)
        ax.text(x, y - 0.10, sub, ha="center", va="center",
                fontsize=7, color=text_color, style="italic")
    else:
        ax.text(x, y, label, ha="center", va="center",
                fontsize=9, fontweight="bold", color=text_color, wrap=True)


def _diamond(ax, x, y, w, h, label, color=C["gate"]):
    pts = [(x, y + h/2), (x + w/2, y), (x, y - h/2), (x - w/2, y)]
    diamond = plt.Polygon(pts, closed=True, facecolor=color,
                          edgecolor=C["border"], linewidth=1.5)
    ax.add_patch(diamond)
    ax.text(x, y, label, ha="center", va="center", fontsize=8,
            fontweight="bold", color=C["text_light"])


def _cylinder(ax, x, y, w, h, label, color=C["store"]):
    rect = FancyBboxPatch((x - w/2, y - h/2), w, h,
                          boxstyle="round,pad=0.04", linewidth=1.5,
                          edgecolor=C["border"], facecolor=color)
    ax.add_patch(rect)
    # top ellipse (cylinder effect)
    ell = mpatches.Ellipse((x, y + h/2), w, h * 0.22,
                            facecolor=color, edgecolor=C["border"], linewidth=1.2)
    ax.add_patch(ell)
    ax.text(x, y, label, ha="center", va="center", fontsize=8.5,
            fontweight="bold", color=C["text_light"])


def _arrow(ax, x1, y1, x2, y2, label="", color=C["arrow"], lw=1.2,
           style="->", linestyle="-", head_width=0.025):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle=style, color=color,
                                lw=lw, linestyle=linestyle,
                                connectionstyle="arc3,rad=0.05"))
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ax.text(mx + 0.03, my, label, fontsize=6.5, color=color,
                ha="left", va="center",
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.7, pad=1))


def _legend(ax, items: list[tuple[str, str]], loc=(0.01, 0.01)):
    handles = [mpatches.Patch(facecolor=c, edgecolor=C["border"], label=l)
               for l, c in items]
    leg = ax.legend(handles=handles, loc="lower left",
                    bbox_to_anchor=loc, fontsize=7,
                    framealpha=0.92, ncol=min(3, len(items)),
                    title="Legend", title_fontsize=7)
    leg.get_frame().set_linewidth(0.5)


def _title(ax, text, subtitle=""):
    ax.set_title(text, fontsize=13, fontweight="bold",
                 color=C["text_dark"], pad=12)
    if subtitle:
        ax.text(0.5, 1.01, subtitle, transform=ax.transAxes,
                ha="center", va="bottom", fontsize=8, color="#555",
                style="italic")


def _setup(w=16, h=10, title="", subtitle=""):
    fig, ax = plt.subplots(figsize=(w, h))
    fig.patch.set_facecolor(C["bg"])
    ax.set_facecolor(C["bg"])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    if title:
        _title(ax, title, subtitle)
    return fig, ax


# ═══════════════════════════════════════════════════════════════════════════════
# D0 MASTER POSTER
# ═══════════════════════════════════════════════════════════════════════════════

def d0_master_poster():
    fig, ax = _setup(20, 12,
        "EchoInsight — Master Architecture",
        "Telecom Conversation Intelligence Platform  |  Vercel + Render + Groq  |  Version 1.0 (code frozen)")

    # Background bands
    bands = [
        (0.0, 0.18, C["band_dep"],   "DEPLOYMENT: Docker · Render free tier · seed restore at boot · Alembic · Vercel"),
        (0.18, 0.34, C["band_obs"],  "OBSERVABILITY & EVAL: /health /ready /metrics · token budget · eval pipeline · CI"),
        (0.34, 0.50, C["band_trust"],"TRUST & SAFETY: redaction boundary · evidence gate · RBAC · prompt injection defense · audit log"),
    ]
    for ylo, yhi, col, lbl in bands:
        rect = mpatches.Rectangle((0, ylo), 1, yhi - ylo,
                                   facecolor=col, edgecolor="none", alpha=0.55, zorder=0)
        ax.add_patch(rect)
        ax.text(0.005, (ylo + yhi) / 2, lbl, fontsize=6.5, color="#333",
                va="center", style="italic")

    # ── User column ──
    for i, (lbl, sub) in enumerate([("Admin", "full access"),
                                     ("Supervisor", "team-scoped"),
                                     ("Agent", "own calls")]):
        y = 0.82 - i * 0.13
        _box(ax, 0.07, y, 0.10, 0.09, lbl, sub, color=C["user"], text_color="#000")

    ax.text(0.07, 0.97, "Users & Roles", ha="center", va="center",
            fontsize=8, fontweight="bold", color="#555")

    # ── Frontend column ──
    fe_items = [
        ("Dashboard\nKPIs · Charts", 0.88),
        ("Conv Detail\nTranscript · QA", 0.76),
        ("Admin Panel\nChecklist · Audit", 0.64),
        ("Live Demo\nScripted", 0.52),
        ("Assistant UI\nChat", 0.42),
    ]
    for lbl, y in fe_items:
        _box(ax, 0.23, y, 0.12, 0.09, lbl, color=C["service"])
    ax.text(0.23, 0.97, "Vercel — React SPA", ha="center", va="center",
            fontsize=8, fontweight="bold", color=C["service"])

    # ── API/Ingest column ──
    api_items = [
        ("Auth & Scope\nJWT · argon2 · RBAC", 0.88, C["deterministic"]),
        ("Ingest & Redact\n9 regex patterns\nPII → tags", 0.76, C["deterministic"]),
        ("State Reducer\npure fn · no DB", 0.64, C["deterministic"]),
        ("Commitment Ledger\nstatus transitions", 0.53, C["deterministic"]),
        ("Worker (5s poll)\nfinal_analysis jobs", 0.42, C["deterministic"]),
        ("Analytics API\nKPIs · Metrics", 0.32, C["deterministic"]),
    ]
    for lbl, y, col in api_items:
        _box(ax, 0.41, y, 0.13, 0.08, lbl, color=col)
    ax.text(0.41, 0.97, "Render — FastAPI (single instance)", ha="center",
            va="center", fontsize=8, fontweight="bold", color=C["service"])

    # ── Analysis pipeline column ──
    pipe_items = [
        ("Final Analysis\nPipeline orchestrator", 0.88, C["deterministic"]),
        ("LLM: SYSTEM_FINAL\nsummary · reasons · commits", 0.77, C["llm"]),
        ("LLM: SYSTEM_QA\n6 checklist items", 0.66, C["llm"]),
        ("Evidence Gate\nexact substring check", 0.55, C["gate"]),
        ("Phrase Matcher\nregex · 4 items", 0.45, C["deterministic"]),
        ("Selective Verify\nLLM: SYSTEM_VERIFIER", 0.35, C["llm"]),
        ("Hard Gate\n7 structural checks", 0.25, C["gate"]),
        ("QA Scorer\nweighted · coverage · cap", 0.14, C["deterministic"]),
    ]
    for lbl, y, col in pipe_items:
        _box(ax, 0.59, y, 0.13, 0.07, lbl, color=col,
             text_color=C["text_light"])
    ax.text(0.59, 0.97, "Analysis Pipeline", ha="center", va="center",
            fontsize=8, fontweight="bold", color="#333")

    # Redaction boundary label
    ax.annotate("", xy=(0.41, 0.76), xytext=(0.53, 0.76),
                arrowprops=dict(arrowstyle="->", color="red", lw=1.5))
    ax.text(0.47, 0.78, "REDACTION\nBOUNDARY\nPII stops here →", ha="center",
            fontsize=6, color="red", fontweight="bold",
            bbox=dict(facecolor="#FFE0E0", edgecolor="red", alpha=0.7, pad=2))

    # ── Database column ──
    _cylinder(ax, 0.77, 0.75, 0.12, 0.16, "PostgreSQL\n20 tables\nRender managed", color=C["store"])
    _cylinder(ax, 0.77, 0.52, 0.12, 0.10, "demo_seed.db\nSQLite snapshot\nrestored at boot", color="#6A9A60")
    _cylinder(ax, 0.77, 0.37, 0.12, 0.09, "checklist_v1.yaml\n6 items · weights", color="#6A9A60")
    ax.text(0.77, 0.97, "Data Stores", ha="center", va="center",
            fontsize=8, fontweight="bold", color=C["store"])

    # ── External providers ──
    _box(ax, 0.93, 0.78, 0.11, 0.09, "Groq API\nOpenAI-compat", color=C["external"])
    _box(ax, 0.93, 0.65, 0.11, 0.07, "OpenRouter\n(higher priority)", color=C["external"],
         linestyle="--")
    _box(ax, 0.93, 0.52, 0.11, 0.07, "GitHub\nSource + CI", color=C["external"])
    ax.text(0.93, 0.97, "External Systems", ha="center", va="center",
            fontsize=8, fontweight="bold", color="#555")

    # ── Optional layers (dashed) ──
    _box(ax, 0.41, 0.22, 0.13, 0.07, "Action Layer\nRisk · PDCA",
         color=C["optional"], text_color="#333", linestyle="--", lw=1.0)
    _box(ax, 0.41, 0.13, 0.13, 0.07, "Assistant\ntool-calling · read-only",
         color=C["optional"], text_color="#333", linestyle="--", lw=1.0)
    ax.text(0.41, 0.28, "Optional Layers", ha="center", fontsize=6.5,
            color="#808080", style="italic")

    # ── Key arrows ──
    _arrow(ax, 0.12, 0.82, 0.17, 0.88, "HTTPS + JWT")
    _arrow(ax, 0.29, 0.76, 0.34, 0.76, "")
    _arrow(ax, 0.48, 0.88, 0.52, 0.88, "")
    _arrow(ax, 0.65, 0.77, 0.71, 0.77, "verified\nresults")
    _arrow(ax, 0.83, 0.75, 0.87, 0.78, "redacted\ntext only")
    _arrow(ax, 0.71, 0.75, 0.83, 0.75, "persist")

    # ── Why this design box ──
    design_text = ("Why this design\n"
                   "• Modular monolith: one deploy, clear boundaries [ADR-003]\n"
                   "• Redact-first: PII never reaches LLM or DB [ADR-005]\n"
                   "• Evidence gate: hallucinations blocked by construction\n"
                   "• Jobs table queue: full visibility, no Celery/Redis [ADR-007]")
    ax.text(0.07, 0.43, design_text, fontsize=7, color="#333",
            va="top", ha="left",
            bbox=dict(facecolor="#F8F8F8", edgecolor="#AAAAAA", pad=4, alpha=0.95))

    # ── Flow numbers ──
    steps = [(0.13, 0.84, "①"), (0.21, 0.84, "②"), (0.30, 0.76, "③"),
             (0.35, 0.76, "④ Redact"), (0.48, 0.76, "⑤ Store"),
             (0.48, 0.70, "⑥ Queue"), (0.53, 0.88, "⑦ Analyse"),
             (0.65, 0.66, "⑧ Gate"), (0.65, 0.55, "⑨ Score"),
             (0.72, 0.70, "⑩ Persist")]
    for sx, sy, st in steps:
        ax.text(sx, sy, st, fontsize=7, color=C["arrow"], fontweight="bold")

    # ── Legend ──
    _legend(ax, [
        ("Service / deterministic code", C["service"]),
        ("LLM call (orange = AI)", C["llm"]),
        ("Validation gate", C["gate"]),
        ("Data store", C["store"]),
        ("External system", C["external"]),
        ("Optional (feature-flagged)", C["optional"]),
    ], loc=(0.0, 0.0))

    _save(fig, "D0_master_poster", dpi=200)


# ═══════════════════════════════════════════════════════════════════════════════
# D1 SYSTEM CONTEXT
# ═══════════════════════════════════════════════════════════════════════════════

def d1_system_context():
    fig, ax = _setup(14, 8, "D1 — System Context",
                     "EchoInsight in its environment: users, the system, and external systems")

    # Centre: The System
    _box(ax, 0.5, 0.55, 0.28, 0.40,
         "EchoInsight\n\nFastAPI backend (Render)\nReact SPA (Vercel)\nPostgreSQL (Render)\nWorker process",
         color=C["service"])

    # Users
    user_defs = [
        (0.08, 0.82, "Admin\nfull access\nvia browser"),
        (0.08, 0.62, "Supervisor\nteam-scoped\nvia browser"),
        (0.08, 0.42, "Agent\nown calls\nvia browser"),
    ]
    for x, y, lbl in user_defs:
        _box(ax, x, y, 0.12, 0.10, lbl, color=C["user"], text_color="#000")
        _arrow(ax, 0.14, y, 0.36, 0.55, "HTTPS + JWT")

    # External systems
    ext = [
        (0.88, 0.82, "Groq / OpenRouter\nLLM provider\n(OpenAI-compat REST)", "redacted text →\n← JSON analysis"),
        (0.88, 0.62, "HuggingFace\nDataset source\n(fetch script only)", "conv IDs\n(manifests only)"),
        (0.88, 0.42, "GitHub\nSource control + CI", "push / PR"),
        (0.88, 0.25, "Vercel\nFrontend hosting", "static build\nfrontend deploy"),
    ]
    for x, y, lbl, data_lbl in ext:
        _box(ax, x, y, 0.17, 0.10, lbl, color=C["external"])
        _arrow(ax, 0.64, 0.55, 0.79, y, data_lbl, color="#555")

    ax.text(0.5, 0.97, "System boundary: thick blue box",
            ha="center", fontsize=7.5, color="#555", style="italic")

    caption = (
        "Step 1: Users access the system via browser (HTTPS, JWT).\n"
        "Step 2: The system sends REDACTED text only to the LLM provider.\n"
        "Step 3: Dataset fetch is a one-time setup step; no raw rows committed.\n"
        "Step 4: GitHub CI validates pushes; Vercel auto-deploys the frontend."
    )
    ax.text(0.01, 0.02, caption, fontsize=7, color="#333", va="bottom")
    _legend(ax, [("EchoInsight system", C["service"]), ("Users", C["user"]),
                 ("External systems", C["external"])])
    _save(fig, "D1_system_context")


# ═══════════════════════════════════════════════════════════════════════════════
# D2 RUNTIME CONTAINERS
# ═══════════════════════════════════════════════════════════════════════════════

def d2_runtime_containers():
    fig, ax = _setup(16, 9, "D2 — Runtime Containers",
                     "Processes, files, and stores that exist at runtime")

    containers = [
        # (x, y, w, h, label, sub, color)
        (0.12, 0.72, 0.18, 0.30, "Browser App\nReact 18 + Vite\nVercel static SPA",
         "routes: / /conversations/:id\n/admin /assistant /live-demo", C["service"]),
        (0.38, 0.78, 0.18, 0.18, "API Process\nFastAPI + uvicorn\nRender Docker",
         "port 8000\n/api/v1/* routes\n/health /ready /metrics", C["service"]),
        (0.38, 0.52, 0.18, 0.18, "Worker Process\npython -m backend.worker.main\nsame Docker image",
         "polls jobs every 5s\nruns final_analysis\nbootstraps checklists", C["service"]),
        (0.65, 0.75, 0.15, 0.22, "PostgreSQL\nRender managed\n(production)",
         "20 tables\nAlembic migrations\nasyncpg driver", C["store"]),
        (0.65, 0.47, 0.15, 0.14, "demo_seed.db\nSQLite snapshot\n(dev / demo)",
         "copied to dev_local.db\nat boot if missing\nbinary in repo", "#6A9A60"),
        (0.65, 0.32, 0.15, 0.10, "Config files\nchecklist_v1.yaml\ntaxonomy.yaml",
         "seeded to DB at startup\nvia bootstrap.py", "#6A9A60"),
        (0.88, 0.70, 0.15, 0.14, "Groq / OpenRouter\nLLM provider\n(external)",
         "primary: qwen/qwen3.8-27b\nverifier: openai/gpt-oss-20b\nredacted text only", C["external"]),
        (0.88, 0.50, 0.15, 0.10, "GET /health\nGET /ready", "in-process\nno external call", C["deterministic"]),
        (0.88, 0.37, 0.15, 0.10, "GET /metrics\nPrometheus ASGI",
         "admin only\nENABLE_METRICS=true", C["deterministic"]),
    ]

    for x, y, w, h, lbl, sub, col in containers:
        _box(ax, x, y, w, h, lbl, sub, color=col)

    arrows = [
        (0.21, 0.72, 0.29, 0.78, "HTTPS + JWT\nREST API"),
        (0.38, 0.68, 0.38, 0.61, "reads jobs\nDB poll"),
        (0.47, 0.78, 0.57, 0.78, "asyncpg\nasync queries"),
        (0.47, 0.58, 0.57, 0.58, "read/write\njobs table"),
        (0.57, 0.47, 0.57, 0.58, "", C["store"]),
        (0.73, 0.75, 0.80, 0.72, "redacted text"),
        (0.47, 0.78, 0.57, 0.42, "seed restore"),
        (0.57, 0.36, 0.47, 0.78, "bootstrap\nchecklist", "#888"),
    ]
    for a in arrows:
        if len(a) == 5:
            _arrow(ax, *a[:4], a[4])
        else:
            _arrow(ax, *a[:4], a[4], color=a[5])

    caption = (
        "How to read: each box is a runtime process or file.\n"
        "Arrows show communication paths and data direction.\n"
        "Green cylinders = data stores. Orange text = LLM calls happen inside Worker via pipeline."
    )
    ax.text(0.01, 0.02, caption, fontsize=7.5, color="#333")
    _legend(ax, [("Service process", C["service"]), ("Data store", C["store"]),
                 ("External", C["external"]), ("File / config", "#6A9A60")])
    _save(fig, "D2_runtime_containers")


# ═══════════════════════════════════════════════════════════════════════════════
# D3 BACKEND COMPONENT DEPENDENCY
# ═══════════════════════════════════════════════════════════════════════════════

def d3_backend_components():
    fig, ax = _setup(16, 9, "D3 — Backend Components & Dependencies",
                     "Packages and their import direction (no cycles). Arrows = depends on.")

    # Layers top-to-bottom
    packages = {
        # (x, y, label, sublabel, color)
        "api":        (0.50, 0.88, "api\n/api/v1/* routes\n9 router files", C["service"]),
        "worker":     (0.20, 0.88, "worker\npolls jobs table\nruns final_analysis", C["service"]),
        "analysis":   (0.50, 0.72, "analysis\npipeline.py\nincremental.py", C["deterministic"]),
        "state":      (0.30, 0.58, "state\nreducer.py\npure function", C["deterministic"]),
        "qa":         (0.70, 0.58, "qa\nscorer · verification\nphrase_matcher", C["deterministic"]),
        "validator":  (0.50, 0.58, "validator\nevidence_gate\nhard_gate", C["gate"]),
        "llm":        (0.85, 0.72, "llm\nclient · prompts\nbudget", C["llm"]),
        "ingest":     (0.18, 0.72, "ingest\nredactor · assignment", C["deterministic"]),
        "models":     (0.50, 0.42, "models\nORM · Pydantic\ndomain_model", C["store"]),
        "config":     (0.20, 0.42, "config\nsettings · YAML files", "#6A9A60"),
        "bootstrap":  (0.80, 0.42, "bootstrap\nchecklist seeding\nidempotent", "#6A9A60"),
        "auth":       (0.70, 0.88, "auth\nargon2 · JWT\nDeps + deps.py", C["service"]),
        "action_layer":(0.35, 0.25, "action_layer\nrisk · PDCA\n[flagged-off]", C["optional"]),
        "assistant":  (0.65, 0.25, "assistant\ntool-calling pipeline\nread-only", C["optional"]),
    }

    for key, (x, y, lbl, col) in packages.items():
        txt_col = C["text_light"] if col not in (C["optional"],) else "#333"
        is_opt = col == C["optional"]
        _box(ax, x, y, 0.14, 0.09, lbl, color=col, text_color=txt_col,
             linestyle="--" if is_opt else "-")

    deps = [
        ("api", "analysis"), ("api", "ingest"), ("api", "state"), ("api", "models"),
        ("api", "auth"), ("api", "config"), ("api", "bootstrap"),
        ("worker", "analysis"), ("worker", "models"),
        ("analysis", "llm"), ("analysis", "qa"), ("analysis", "validator"),
        ("analysis", "state"), ("analysis", "models"),
        ("qa", "llm"), ("qa", "config"),
        ("state", "models"),
        ("validator", "models"),
        ("llm", "config"),
        ("ingest", "models"),
        ("bootstrap", "models"), ("bootstrap", "config"),
        ("action_layer", "models"), ("action_layer", "llm"),
        ("assistant", "models"), ("assistant", "llm"),
    ]

    for src, dst in deps:
        sx, sy, _, cs = packages[src]
        dx, dy, _, cd = packages[dst]
        opt = cs == C["optional"] or cd == C["optional"]
        _arrow(ax, sx, sy - 0.045, dx, dy + 0.045,
               color="#999" if opt else C["arrow"],
               linestyle="--" if opt else "-")

    caption = (
        "Read: arrows point from dependent to dependency (A → B means A imports B).\n"
        "No cycles exist. 'models' is the shared data layer.\n"
        "Dashed boxes/arrows = optional feature-flagged packages."
    )
    ax.text(0.01, 0.02, caption, fontsize=7.5, color="#333")
    _legend(ax, [("API / Worker layer", C["service"]), ("Deterministic logic", C["deterministic"]),
                 ("LLM client", C["llm"]), ("Validation gates", C["gate"]),
                 ("Data / Config", C["store"]), ("Optional (flagged)", C["optional"])])
    _save(fig, "D3_backend_components")


# ═══════════════════════════════════════════════════════════════════════════════
# D4 ANALYSIS PIPELINE DATA FLOW
# ═══════════════════════════════════════════════════════════════════════════════

def d4_pipeline():
    fig, ax = _setup(18, 10, "D4 — Analysis Pipeline Data Flow",
                     "Numbered steps: per-turn incremental mode (left) and final analysis mode (right)")

    # ── Incremental path (left) ──
    incr = [
        (0.12, 0.88, "① POST /turns\nBrowser → API", C["service"]),
        (0.12, 0.76, "② Redact PII\n9 regex patterns", C["deterministic"]),
        (0.12, 0.64, "③ Store turn\nDB:turns", C["store"]),
        (0.12, 0.52, "④ Queue job\nper_turn_extraction", C["deterministic"]),
        (0.12, 0.40, "⑤ Worker picks up\npoll every 5s", C["deterministic"]),
        (0.12, 0.28, "⑥ LLM: SYSTEM_TURN\n~171 tokens · qwen", C["llm"]),
        (0.12, 0.16, "⑦ Reducer (pure fn)\napply_turn_extraction()", C["deterministic"]),
    ]
    for x, y, lbl, col in incr:
        _box(ax, x, y, 0.17, 0.08, lbl, color=col)
    for i in range(len(incr) - 1):
        _arrow(ax, incr[i][0], incr[i][1] - 0.04, incr[i+1][0], incr[i+1][1] + 0.04)

    ax.text(0.12, 0.97, "INCREMENTAL (per turn)", ha="center",
            fontsize=9, fontweight="bold", color="#555")

    # ── Final path (right) ──
    final = [
        (0.50, 0.94, "① POST /end\nqueue final_analysis", C["service"]),
        (0.50, 0.83, "② Load all turns\nfrom DB:turns", C["deterministic"]),
        (0.50, 0.73, "③ >40 turns?\nWindow (40, overlap=5)", C["gate"]),
        (0.50, 0.62, "④ LLM: SYSTEM_FINAL\nqwen · FINAL_ANALYSIS_SCHEMA", C["llm"]),
        (0.50, 0.52, "⑤ D14 fix: all-neutral\ntrajectory fallback", C["deterministic"]),
        (0.50, 0.42, "⑥ Evidence gate\ncommitments · exact substring", C["gate"]),
        (0.50, 0.32, "⑦ LLM: SYSTEM_QA\n6 checklist items · QA_SCHEMA", C["llm"]),
        (0.50, 0.22, "⑧ Evidence gate\nQA items", C["gate"]),
        (0.50, 0.12, "⑨ Phrase matcher\n4 items · deterministic override", C["deterministic"]),
    ]
    right = [
        (0.78, 0.32, "⑩ Selective verify\nSYSTEM_VERIFIER\nverifier model", C["llm"]),
        (0.78, 0.22, "⑪ Confidence norm\nD7 fix", C["deterministic"]),
        (0.78, 0.12, "⑫ Hard gate\n7 structural checks", C["gate"]),
        (0.78, 0.02, "⑬ QA Scorer\ncoverage · cap · persist", C["deterministic"]),
    ]
    for x, y, lbl, col in final:
        _box(ax, x, y, 0.17, 0.07, lbl, color=col)
    for i in range(len(final) - 1):
        _arrow(ax, final[i][0], final[i][1] - 0.035, final[i+1][0], final[i+1][1] + 0.035)

    for x, y, lbl, col in right:
        _box(ax, x, y, 0.17, 0.07, lbl, color=col)
    _arrow(ax, final[-1][0], final[-1][1] - 0.035, right[0][0], right[0][1] + 0.035)
    for i in range(len(right) - 1):
        _arrow(ax, right[i][0], right[i][1] - 0.035, right[i+1][0], right[i+1][1] + 0.035)

    ax.text(0.50, 0.99, "FINAL ANALYSIS (on conversation end)", ha="center",
            fontsize=9, fontweight="bold", color="#555")

    # needs_review fallback arrows
    _arrow(ax, 0.59, 0.42, 0.70, 0.38, "quote mismatch →\nneeds_review", color="red",
           linestyle="--")
    _arrow(ax, 0.78, 0.15, 0.65, 0.10, "fail →\nhuman_review_required", color="red",
           linestyle="--")

    # Long-call windowing note
    ax.text(0.35, 0.73, "window=40, overlap=5\nper-window merge\n→ deduplicate by turn_id",
            fontsize=6.5, color="#555",
            bbox=dict(facecolor="#F8F8F8", edgecolor="#ccc", pad=2))

    caption = ("LLM calls shown in orange. Deterministic steps in blue. Gates in red.\n"
               "Failure path (dashed red): invalid quote → needs_review → human review flag set.\n"
               "D14 fix: if final LLM returns all-neutral sentiment, fall back to incremental trajectory.")
    ax.text(0.01, 0.0, caption, fontsize=7, color="#333")
    _legend(ax, [("Deterministic", C["service"]), ("LLM call", C["llm"]),
                 ("Validation gate", C["gate"]), ("Data store", C["store"])])
    _save(fig, "D4_analysis_pipeline")


# ═══════════════════════════════════════════════════════════════════════════════
# D5 CONVERSATION LIFECYCLE STATE MACHINE
# ═══════════════════════════════════════════════════════════════════════════════

def d5_state_machine():
    fig, ax = _setup(14, 8, "D5 — Conversation Lifecycle State Machine",
                     "domain_model.py:ConversationStatus  |  worker/main.py idle sweep + 72h close")

    states = {
        "created":  (0.15, 0.55),
        "active":   (0.38, 0.55),
        "ended":    (0.62, 0.55),
        "closed":   (0.85, 0.55),
        "resumed":  (0.50, 0.25),
    }
    colors = {
        "created": C["deterministic"], "active": "#5A8A50",
        "ended": C["llm"], "closed": "#808080", "resumed": "#6A4A9A"
    }
    for name, (x, y) in states.items():
        is_opt = name == "resumed"
        _box(ax, x, y, 0.17, 0.12, name.upper(),
             color=colors[name], linestyle="--" if is_opt else "-")

    transitions = [
        ("created", "active", "POST /turns\n(first turn appended)"),
        ("active", "ended", "POST /{id}/end\n(explicit end)"),
        ("ended", "closed", "72 h elapsed\n(worker sweep)"),
    ]
    for src, dst, lbl in transitions:
        sx, sy = states[src]
        dx, dy = states[dst]
        _arrow(ax, sx + 0.085, sy, dx - 0.085, dy, lbl)

    # Active → ended (idle timeout)
    _arrow(ax, 0.38, 0.49, 0.62, 0.49, "idle 30 min\n(worker sweep)", color="#888")

    # ended → resumed (Tier 2, dashed)
    _arrow(ax, 0.62, 0.49, 0.50, 0.31, "POST /resume\n(Tier 2)", color="#6A4A9A", linestyle="--")
    _arrow(ax, 0.50, 0.31, 0.38, 0.49, "status → active\n(new segment)", color="#6A4A9A", linestyle="--")

    # End reasons
    ax.text(0.62, 0.72, "end_reason:\n• normal\n• abandoned\n• transfer\n• escalation\n• idle_timeout",
            fontsize=7, color="#333",
            bbox=dict(facecolor="#FFF9E6", edgecolor="#ccc", pad=3))

    ax.text(0.50, 0.13, "Dashed = Tier 2 (implemented in domain model, not in active use)",
            ha="center", fontsize=7, color="#808080", style="italic")

    caption = ("Worker idle sweep: marks active conversations ended after 30 min without a new turn.\n"
               "Worker close sweep: marks ended conversations closed after 72 h.\n"
               "Resume (dashed): Tier 2 feature; code path exists but not triggered by current demo.")
    ax.text(0.01, 0.02, caption, fontsize=7.5, color="#333")
    _legend(ax, [("Normal state", C["service"]), ("Active", "#5A8A50"),
                 ("Ended", C["llm"]), ("Closed", "#808080"), ("Tier 2 / optional", "#6A4A9A")])
    _save(fig, "D5_state_machine")


# ═══════════════════════════════════════════════════════════════════════════════
# D6 COMMITMENT LEDGER TRANSITIONS
# ═══════════════════════════════════════════════════════════════════════════════

def d6_commitment():
    fig, ax = _setup(14, 8, "D6 — Commitment Ledger Status Transitions",
                     "models.py:CommitmentStatus  |  state/reducer.py  |  analysis/pipeline.py")

    states = {
        "proposed":   (0.20, 0.60),
        "accepted":   (0.42, 0.78),
        "scheduled":  (0.42, 0.42),
        "completed":  (0.70, 0.60),
        "cancelled":  (0.70, 0.35),
        "uncertain":  (0.70, 0.85),
    }
    colors = {
        "proposed": C["deterministic"], "accepted": "#5A8A50",
        "scheduled": "#6A4A9A", "completed": "#2ECC71",
        "cancelled": C["gate"], "uncertain": "#D4AC0D",
    }
    for name, (x, y) in states.items():
        _box(ax, x, y, 0.17, 0.11, name.upper(), color=colors[name])

    transitions = [
        ("proposed", "accepted", "customer confirms"),
        ("proposed", "scheduled", "date/time set"),
        ("proposed", "completed", "agent marks done\nor LLM detects"),
        ("proposed", "cancelled", "customer rejects\nor cancelled"),
        ("accepted", "scheduled", "specific time set"),
        ("scheduled", "completed", "confirmed done"),
        ("accepted", "completed", "completed directly"),
        ("proposed", "uncertain", "LLM ambiguous"),
    ]
    for src, dst, lbl in transitions:
        sx, sy = states[src]
        dx, dy = states[dst]
        _arrow(ax, sx + 0.085, sy, dx - 0.085, dy, lbl, color="#333")

    # D4 fix note
    ax.text(0.01, 0.15,
            "D4 fix (analysis/pipeline.py:356-366):\n"
            "Non-provisional commitments are DELETED then re-inserted\n"
            "on each final_analysis run to prevent duplicate ledger entries.",
            fontsize=7.5, color="#333",
            bbox=dict(facecolor="#FFF0F0", edgecolor="#C00", pad=3))

    # Provisional flag
    ax.text(0.01, 0.88,
            "provisional=True: set during per-turn extraction\n"
            "provisional=False: set by final_analysis pipeline\n"
            "(final analysis replaces provisional commitments)",
            fontsize=7.5, color="#333",
            bbox=dict(facecolor="#EBF5FB", edgecolor="#2E75B6", pad=3))

    caption = ("Commitments created by LLM per-turn extraction start as proposed+provisional.\n"
               "The final analysis pipeline replaces all provisional commitments with the final set.")
    ax.text(0.01, 0.02, caption, fontsize=7.5, color="#333")
    _legend(ax, [("proposed", C["deterministic"]), ("accepted", "#5A8A50"),
                 ("scheduled", "#6A4A9A"), ("completed", "#2ECC71"),
                 ("cancelled", C["gate"]), ("uncertain", "#D4AC0D")])
    _save(fig, "D6_commitment_ledger")


# ═══════════════════════════════════════════════════════════════════════════════
# D7 QA SCORING FLOW
# ═══════════════════════════════════════════════════════════════════════════════

def d7_qa_scoring():
    fig, ax = _setup(18, 10, "D7 — QA Scoring Flow",
                     "qa/scorer.py · qa/phrase_matcher.py · qa/verification.py · validator/evidence_gate.py")

    steps = [
        (0.12, 0.88, "LLM: SYSTEM_QA\nScore 6 checklist items\nresult · quote · confidence", C["llm"]),
        (0.12, 0.74, "Evidence Gate\ncheck_quote():\nnormalized substring?", C["gate"]),
        (0.12, 0.60, "Phrase Matcher\nregex deterministic check\n4 items (greeting, etc.)", C["deterministic"]),
        (0.12, 0.46, "Selective Verification\n_should_verify():\ncritical? low-conf? absence?", C["deterministic"]),
        (0.12, 0.32, "LLM: SYSTEM_VERIFIER\nverifier model (gpt-oss-20b)\nper-item second opinion", C["llm"]),
        (0.12, 0.18, "Confidence Normalisation\nD7 fix: override constant 0.9\nbased on evidence strength", C["deterministic"]),
        (0.12, 0.05, "Hard Gate\n7 structural checks\nall_fail → human_review", C["gate"]),
    ]

    right_steps = [
        (0.55, 0.74, "quote mismatch →\nresult = needs_review\nevidence_flag = quote_mismatch", C["gate"]),
        (0.55, 0.46, "Routes: critical items,\nabsence evidence,\nconf < 0.75,\nopen commits+resolved,\nneeds_review", C["llm"]),
        (0.55, 0.32, "Verdict: supported\nnot_supported → needs_review\ninsufficient → human_review", C["llm"]),
    ]

    scorer_box = (0.42, 0.05, 0.50, 0.12,
                  "QA Scorer: qa/scorer.py\n"
                  "coverage = assessed / applicable\n"
                  "score = (passed_wt / assessed_wt) × 100\n"
                  "if critical_violation: score = min(score, 60)\n"
                  "if coverage < 0.70: label = partial (×0.5 penalty)\n"
                  "if applicable_wt = 0: label = not_assessed")

    for x, y, lbl, col in steps:
        _box(ax, x, y, 0.20, 0.09, lbl, color=col)
    for i in range(len(steps) - 1):
        _arrow(ax, steps[i][0], steps[i][1] - 0.045, steps[i+1][0], steps[i+1][1] + 0.045)

    for x, y, lbl, col in right_steps:
        _box(ax, x, y, 0.26, 0.09, lbl, color=col)

    _arrow(ax, 0.22, 0.74, 0.42, 0.74, "fail", color="red", linestyle="--")
    _arrow(ax, 0.22, 0.46, 0.42, 0.46, "route", color=C["llm"])
    _arrow(ax, 0.22, 0.32, 0.42, 0.32, "verdict")

    # Scorer box
    xs, ys, ws, hs, scorer_lbl = scorer_box
    _box(ax, xs, ys, ws, hs, scorer_lbl, color="#EBF5FB",
         text_color="#000", lw=2)

    # Checklist weights table
    weights_text = ("Checklist item weights:\n"
                    "greeting           1.0  critical=N\n"
                    "identity_verify    2.0  critical=Y\n"
                    "empathy            1.5  critical=N\n"
                    "disclosure         1.5  critical=Y\n"
                    "prohib_promises    2.0  critical=Y\n"
                    "closure            1.0  critical=N")
    ax.text(0.70, 0.96, weights_text, fontsize=7.5, va="top",
            fontfamily="monospace",
            bbox=dict(facecolor="#F8F8F8", edgecolor="#888", pad=4))

    caption = ("Key: evidence gate runs before scoring. A failed quote → needs_review (not counted as assessed).\n"
               "Critical violation cap: if identity_verify, disclosure or prohibited_promises fails → score ≤ 60.\n"
               "Coverage < 70% → label='partial' and needs_review coverage penalty ×0.5 applied.")
    ax.text(0.01, 0.0, caption, fontsize=7.5, color="#333")
    _legend(ax, [("LLM call", C["llm"]), ("Deterministic", C["deterministic"]),
                 ("Gate / failure path", C["gate"])])
    _save(fig, "D7_qa_scoring")


# ═══════════════════════════════════════════════════════════════════════════════
# D8a SEQUENCE: TURN APPEND
# ═══════════════════════════════════════════════════════════════════════════════

def d8_sequence():
    fig, ax = _setup(18, 10, "D8 — Sequence Diagrams",
                     "(a) Turn Append   (b) Final Analysis on End   (c) Analytics   (d) Failure Path")

    # Draw as simplified swim-lane tables

    lanes = ["Browser", "API\n/turns", "Redactor", "DB", "Worker", "LLM"]
    x_pos = [0.07, 0.22, 0.37, 0.52, 0.67, 0.82]
    y_top = 0.96
    y_bot = 0.02

    # Draw swimlane headers and vertical lifelines
    for i, (lane, x) in enumerate(zip(lanes, x_pos)):
        _box(ax, x, y_top, 0.12, 0.05, lane, color=C["service"] if i < 2 else
             (C["deterministic"] if i < 4 else (C["store"] if i == 3 else
             (C["deterministic"] if i == 4 else C["llm"]))))
        ax.plot([x, x], [y_top - 0.025, y_bot + 0.02], color="#AAA",
                linewidth=1, linestyle="--", zorder=0)

    # Turn append sequence (top half)
    seq_a = [
        (0.07, 0.22, 0.85, "a1. POST /turns {speaker, text, idempotency_key}"),
        (0.22, 0.37, 0.78, "a2. redact_turn(speaker, text) → text_redacted"),
        (0.37, 0.52, 0.72, "a3. INSERT turn (text_redacted, hash, seq)"),
        (0.52, 0.37, 0.66, "a4. INSERT job (per_turn_extraction)"),
        (0.07, 0.22, 0.60, "a5. ← 201 {turn, provisional_state}"),
        (0.67, 0.52, 0.53, "a6. poll: SELECT queued jobs"),
        (0.67, 0.82, 0.47, "a7. chat_json(SYSTEM_TURN, context)"),
        (0.82, 0.67, 0.41, "a8. ← extraction JSON"),
        (0.67, 0.52, 0.35, "a9. UPDATE provisional_state_json"),
    ]

    for x1, x2, y, lbl in seq_a:
        going_right = x2 > x1
        _arrow(ax, x1 + (0.06 if going_right else -0.06), y,
               x2 - (0.06 if going_right else -0.06), y,
               label="", color=C["arrow"])
        ax.text((x1 + x2) / 2, y + 0.015, lbl, ha="center", fontsize=6.5,
                color="#333",
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.7, pad=1))

    # Final analysis sequence (bottom half — abbreviated)
    seq_b = [
        (0.07, 0.22, 0.30, "b1. POST /end → INSERT job (final_analysis)"),
        (0.67, 0.52, 0.25, "b2. SELECT turns, build transcript"),
        (0.67, 0.82, 0.20, "b3. SYSTEM_FINAL → analysis JSON"),
        (0.67, 0.82, 0.15, "b4. SYSTEM_QA → QA items JSON"),
        (0.67, 0.52, 0.10, "b5. persist Analysis + QAResult + Commitments"),
    ]
    for x1, x2, y, lbl in seq_b:
        going_right = x2 > x1
        _arrow(ax, x1 + (0.06 if going_right else -0.06), y,
               x2 - (0.06 if going_right else -0.06), y,
               label="", color="#5A8A50")
        ax.text((x1 + x2) / 2, y + 0.013, lbl, ha="center", fontsize=6.5,
                color="#3A6A30",
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.7, pad=1))

    # Section labels
    ax.text(0.01, 0.88, "a. Turn Append\n   (incremental)", fontsize=7.5,
            fontweight="bold", color=C["arrow"])
    ax.text(0.01, 0.32, "b. Final Analysis\n   on end", fontsize=7.5,
            fontweight="bold", color="#3A6A30")

    ax.text(0.50, 0.0,
            "Step a7 is the only LLM call in the turn-append path. Steps b3 and b4 are the two LLM calls in final analysis. "
            "Browser unblocked at step a5; LLM runs async.",
            fontsize=7, color="#333", ha="center")

    _save(fig, "D8_sequence_diagrams")


# ═══════════════════════════════════════════════════════════════════════════════
# D9 DATA MODEL (ER DIAGRAM)
# ═══════════════════════════════════════════════════════════════════════════════

def d9_data_model():
    fig, ax = _setup(18, 11, "D9 — Data Model",
                     "Key tables, relations, unique constraints, and seed counts  |  backend/models.py")

    tables = {
        "users":       (0.10, 0.82, "users\nid · username · role\nagent_id · team_id", 5),
        "agents":      (0.10, 0.63, "agents\nagent_id · display_name\nteam_id · synthetic", 25),
        "teams":       (0.10, 0.44, "teams\nteam_id · display_name\nsynthetic", 5),
        "conversations":(0.32, 0.72, "conversations\nid · source_id\nagent_id · team_id\nstatus · provisional_state_json\nanalysis_version", 49),
        "turns":       (0.32, 0.48, "turns\nturn_id · seq\nconversation_id\ntext_redacted · content_hash\nidempotency_key", 264),
        "analyses":    (0.55, 0.80, "analyses\nanalysis_id · conversation_id\nversion · model\nsummary · resolution\nchurn_risk · false_resolution", 57),
        "qa_results":  (0.55, 0.60, "qa_results\nqa_result_id · analysis_id\nscore · score_label\ncoverage · critical_violation\nitems_json", 57),
        "commitments": (0.55, 0.40, "commitments\ncommitment_id\nconversation_id\ndescription · status\nprovisional", 68),
        "jobs":        (0.32, 0.28, "jobs\njob_id · job_type\nstatus · attempts\nconversation_id\nerror", 0),
        "audit_log":   (0.78, 0.72, "audit_log\nid · user_id\naction · resource_type\nresource_id · details_json", 277),
        "qa_checklist":(0.78, 0.54, "qa_checklist\nqa_checklist_version\nqa_checklist_item\n(3-table hierarchy)", 0),
        "cases":       (0.78, 0.36, "cases\ncase_id · title · status\n↔ case_conversations", 0),
        "review_ann":  (0.78, 0.20, "review_annotations\nreview_id · conversation_id\nreviewer_id · verdict", 0),
        "asst":        (0.32, 0.10, "asst_session\nasst_message · asst_feedback\n(assistant tables)", 0),
    }

    for name, (x, y, lbl, count) in tables.items():
        col = C["store"] if count > 0 else "#6A9A60"
        count_str = f"\n[seed: {count}]" if count > 0 else "\n[0 in seed]"
        _box(ax, x, y, 0.20, 0.13, lbl + count_str, color=col)

    rels = [
        ("users", "conversations", "1:N via agent_id"),
        ("teams", "agents", "1:N"),
        ("agents", "conversations", "1:N"),
        ("conversations", "turns", "1:N"),
        ("conversations", "analyses", "1:N"),
        ("conversations", "commitments", "1:N"),
        ("conversations", "jobs", "1:N"),
        ("analyses", "qa_results", "1:1"),
        ("users", "audit_log", "1:N"),
    ]
    for src, dst, lbl in rels:
        sx, sy, _, _ = tables[src]
        dx, dy, _, _ = tables[dst]
        _arrow(ax, sx + 0.10, sy, dx - 0.10, dy, lbl, color="#555")

    # Unique constraint callouts
    ax.text(0.01, 0.12,
            "Key constraints:\n"
            "• turns: UNIQUE(conv_id, seq), UNIQUE(conv_id, idempotency_key)\n"
            "• analyses: UNIQUE(conv_id, version)\n"
            "• qa_checklist_version: UNIQUE(checklist_id, version_number)\n"
            "• Content hash = SHA-256(text_redacted) — no original text stored",
            fontsize=7.5, color="#333",
            bbox=dict(facecolor="#EBF5FB", edgecolor="#2E75B6", pad=4))

    ax.text(0.01, 0.30,
            "sa.JSON used for all JSON columns\n(works on both SQLite and PostgreSQL)\nNo sa.JSONB — portable ORM",
            fontsize=7, color="#555",
            bbox=dict(facecolor="#FFF9E6", edgecolor="#ccc", pad=3))

    caption = ("Green = in demo seed. Dark green = 0 rows in seed but table exists.\n"
               "Counts from proceedings.md. state_events table: 0 rows in seed (append-only log not yet populated).")
    ax.text(0.01, 0.01, caption, fontsize=7.5, color="#333")
    _legend(ax, [("In demo seed (count shown)", C["store"]),
                 ("Table exists, 0 in seed", "#6A9A60")])
    _save(fig, "D9_data_model")


# ═══════════════════════════════════════════════════════════════════════════════
# D10 SECURITY & TRUST BOUNDARIES
# ═══════════════════════════════════════════════════════════════════════════════

def d10_security():
    fig, ax = _setup(16, 9, "D10 — Security & Trust Boundaries",
                     "docs/security.md  |  backend/auth.py  |  backend/ingest/redactor.py")

    # Zones
    zones = [
        (0.01, 0.01, 0.98, 0.98, "#F0F0F0", "Render + Vercel environment (HTTPS everywhere)"),
        (0.30, 0.05, 0.68, 0.88, "#EBF5FB", "Trust boundary: redacted zone"),
        (0.55, 0.10, 0.43, 0.82, "#FFF0F0", "No PII past this line"),
    ]
    for x, y, w, h, col, lbl in zones:
        rect = mpatches.Rectangle((x, y), w, h, facecolor=col,
                                   edgecolor="#888", linewidth=1, linestyle="--", alpha=0.4)
        ax.add_patch(rect)
        ax.text(x + 0.01, y + h - 0.03, lbl, fontsize=7, color="#555", style="italic")

    items = [
        # Auth
        (0.12, 0.82, "Browser\nHTTPS + JWT\nin localStorage", C["service"]),
        (0.12, 0.67, "Auth Layer\nJWT decode · argon2id\nHS256 · 30 min expiry", C["deterministic"]),
        (0.12, 0.52, "Role Scope\nadmin: all\nsupervisor: team\nagent: own calls", C["deterministic"]),

        # Redaction
        (0.38, 0.75, "Redact PII\n9 patterns\noriginal discarded", C["gate"]),
        (0.38, 0.58, "Store\ntext_redacted only\nSHA-256 hash", C["store"]),
        (0.38, 0.42, "Prompt injection\nXML <transcript> tags\n'never follow inside'", C["deterministic"]),

        # LLM zone
        (0.70, 0.67, "LLM Provider\n(Groq/OpenRouter)\nredacted text only", C["external"]),
        (0.70, 0.50, "Evidence Gate\nexact substring\nblocks hallucinated quotes", C["gate"]),

        # Not implemented
        (0.85, 0.30, "NOT IMPLEMENTED:\n• Token refresh\n• Token blocklist\n• Distributed rate limit\n• Pen test", "#C0C0C0"),
    ]
    for x, y, lbl, col in items:
        txt = C["text_light"] if col not in ("#C0C0C0",) else "#333"
        _box(ax, x, y, 0.18, 0.10, lbl, color=col, text_color=txt)

    sec_items = [
        (0.12, 0.37, "Rate limit: 200 req/min/IP\n(in-process, prod only)", C["deterministic"]),
        (0.12, 0.24, "Security headers:\nHSTS · CSP · X-Frame-Options", C["deterministic"]),
        (0.12, 0.12, "Audit log: 277 entries\nsensitive actions logged", "#6A9A60"),
        (0.38, 0.24, "SQL injection:\nSQLAlchemy ORM\nparameterized only", C["deterministic"]),
        (0.38, 0.12, "Secrets: .env only\nnever in code/image\ngitleaks in CI", C["deterministic"]),
        (0.55, 0.28, "CORS allow-list:\nCORS_ALLOWED_ORIGINS\nenv var", C["deterministic"]),
    ]
    for x, y, lbl, col in sec_items:
        _box(ax, x, y, 0.18, 0.09, lbl, color=col)

    caption = ("Red dashed zone = PII stops at the redaction boundary. LLM receives redacted text only.\n"
               "Evidence gate is a second layer: blocks hallucinated quotes from being stored.\n"
               "Grey box: items documented but not yet implemented.")
    ax.text(0.01, 0.01, caption, fontsize=7.5, color="#333")
    _legend(ax, [("Implemented", C["deterministic"]), ("Gate", C["gate"]),
                 ("External", C["external"]), ("Not implemented", "#C0C0C0")])
    _save(fig, "D10_security")


# ═══════════════════════════════════════════════════════════════════════════════
# D11 DEPLOYMENT TOPOLOGY
# ═══════════════════════════════════════════════════════════════════════════════

def d11_deployment():
    fig, ax = _setup(16, 9, "D11 — Deployment Topology",
                     "render.yaml · docker-compose.prod.yml · frontend/vercel.json")

    nodes = [
        (0.10, 0.72, "Developer\nworkstation", C["user"]),
        (0.28, 0.88, "GitHub\nrepo + CI\n(.github/workflows)", C["external"]),
        (0.28, 0.55, "Vercel\nStatic SPA\nnginx-served Vite build\nfrontend/vercel.json", C["service"]),
        (0.55, 0.88, "Render.com\nDocker web service\nsingle instance, free tier\nrender.yaml", C["service"]),
        (0.55, 0.60, "API Process\nuvicorn :8000\nalembic upgrade head\nseed on startup", C["deterministic"]),
        (0.55, 0.40, "Worker Process\npython -m backend.worker.main\nsame Docker image", C["deterministic"]),
        (0.80, 0.78, "Render PostgreSQL\nmanaged, free tier\nasyncpg driver\nRender provided URL", C["store"]),
        (0.80, 0.48, "demo_seed.db\nNOT on Render FS\nSEED_DEMO_DATA=true\nfor idempotent seed", "#6A9A60"),
        (0.28, 0.28, "End User\nbrowser", C["user"]),
        (0.80, 0.28, "Groq / OpenRouter\nexternal LLM API", C["external"]),
    ]
    for x, y, lbl, col in nodes:
        _box(ax, x, y, 0.18, 0.13, lbl, color=col,
             text_color=C["text_light"] if col not in (C["user"],) else "#000")

    arrows = [
        (0.10, 0.78, 0.28, 0.88, "git push"),
        (0.28, 0.88, 0.55, 0.88, "auto-deploy\n(Docker build)"),
        (0.28, 0.88, 0.28, 0.62, "npm build\n→ Vercel deploy"),
        (0.55, 0.88, 0.55, 0.67, "docker run"),
        (0.55, 0.60, 0.55, 0.47, "shared image"),
        (0.55, 0.68, 0.80, 0.78, "asyncpg"),
        (0.55, 0.47, 0.80, 0.52, "asyncpg"),
        (0.28, 0.35, 0.28, 0.48, "HTTPS"),
        (0.37, 0.55, 0.46, 0.60, "VITE_API_URL\nCORS"),
        (0.64, 0.60, 0.71, 0.55, "LLM calls\nredacted only"),
        (0.80, 0.55, 0.80, 0.28, "same provider"),
    ]
    for a in arrows:
        _arrow(ax, *a[:4], a[4] if len(a) > 4 else "")

    # Boot sequence
    ax.text(0.01, 0.18,
            "Startup sequence (Render):\n"
            "1. Docker container starts\n"
            "2. alembic upgrade head (subprocess)\n"
            "3. seed_users() from SEED_USERS env\n"
            "4. bootstrap_qa_checklists()\n"
            "5. seed_demonstration() if SEED_DEMO_DATA=true\n"
            "6. uvicorn ready to serve",
            fontsize=7.5, color="#333",
            bbox=dict(facecolor="#EBF5FB", edgecolor="#2E75B6", pad=4))

    ax.text(0.01, 0.04,
            "Cold start: Render free tier spins down after 15 min inactivity. First request: 30-60s delay.\n"
            "CORS: CORS_ALLOWED_ORIGINS=https://echoinsight-telecom-intelligence.vercel.app",
            fontsize=7, color="#555")

    _legend(ax, [("Service", C["service"]), ("Process", C["deterministic"]),
                 ("Data store", C["store"]), ("External", C["external"])])
    _save(fig, "D11_deployment")


# ═══════════════════════════════════════════════════════════════════════════════
# D12 OBSERVABILITY
# ═══════════════════════════════════════════════════════════════════════════════

def d12_observability():
    fig, ax = _setup(16, 9, "D12 — Observability, Evaluation & CI",
                     "health · metrics · audit log · eval pipeline · test layers · CI")

    items = [
        # Observability
        (0.12, 0.85, "GET /health\nDB ping · timestamp\n{status: ok}", C["deterministic"]),
        (0.12, 0.70, "GET /ready\nmigration version\n{status: ready}", C["deterministic"]),
        (0.12, 0.55, "GET /metrics\nPrometheus ASGI\nadmin only", C["deterministic"]),
        (0.12, 0.40, "structlog\nJSON in prod\nrequest_id per line", C["deterministic"]),
        (0.12, 0.25, "Audit log DB\nall sensitive actions\n277 entries in seed", "#6A9A60"),
        (0.12, 0.10, "Admin health page\ntoken budget · job depth\nUI admin panel", C["service"]),

        # Eval pipeline
        (0.40, 0.85, "Token budget\n400k/day in-process\nlru_cache reset daily", C["llm"]),
        (0.40, 0.70, "Eval pipeline\nevals/run_eval.py\nmake eval", C["deterministic"]),
        (0.40, 0.55, "Gold workbook\nevals/gold_workbook.csv\nNOT YET ANNOTATED", C["gate"]),
        (0.40, 0.40, "Rubric\nevals/rubric.md\nannotation guide", "#6A9A60"),
        (0.40, 0.25, "Eval result\neval_20261002T105635Z.json\nsample_size=0 · provisional", C["gate"]),
        (0.40, 0.10, "Analysis pool\n147 conversations · seed=42\n36 gold (13 dev + 23 test)", "#6A9A60"),

        # Test layers
        (0.68, 0.85, "Unit tests\n~45 tests · <1s\nno LLM · no DB", C["deterministic"]),
        (0.68, 0.72, "Integration tests\n~11 tests · 2-3s\nSQLite in-memory", C["deterministic"]),
        (0.68, 0.59, "Security tests\nauthentication · scoping\ncross-team access", C["gate"]),
        (0.68, 0.45, "Leakage check\ntest IDs not in prompts\ngold-set isolation", C["gate"]),
        (0.68, 0.32, "Phase 0 audit\n259 tests passed\n~21 seconds total", "#5A8A50"),
        (0.68, 0.19, "CI gates\n.github/workflows\nlint + test + build", C["service"]),
        (0.68, 0.06, "pytest command\npython -m pytest tests/ -v", "#6A9A60"),

        # Known gaps
        (0.88, 0.55, "NOT RUN:\n• Load test (100 concurrent)\n• p50/p95 at prod load\n• Real-model latency\n• F1 metrics (need gold)", "#C0C0C0"),
    ]
    for x, y, lbl, col in items:
        txt = C["text_light"] if col not in ("#6A9A60", "#C0C0C0", "#5A8A50") else (
            "#333" if col == "#C0C0C0" else C["text_light"])
        _box(ax, x, y, 0.22, 0.10, lbl, color=col, text_color=txt)

    # Section headers
    ax.text(0.12, 0.97, "Observability", ha="center", fontsize=9, fontweight="bold")
    ax.text(0.40, 0.97, "Evaluation Pipeline", ha="center", fontsize=9, fontweight="bold")
    ax.text(0.68, 0.97, "Test Layers", ha="center", fontsize=9, fontweight="bold")
    ax.text(0.88, 0.65, "Gaps", ha="center", fontsize=9, fontweight="bold", color="red")

    caption = ("Gold workbook (evals/gold_workbook.csv) requires human annotation before F1 metrics can be computed.\n"
               "Token budget counter is in-process only — not shared across restarts or multiple workers (known limit).\n"
               "Red boxes = known gaps: eval sample_size=0, gold not annotated, load test not run.")
    ax.text(0.01, 0.01, caption, fontsize=7.5, color="#333")
    _legend(ax, [("Implemented", C["deterministic"]), ("Gap / not run", C["gate"]),
                 ("Passed", "#5A8A50"), ("Not yet done", "#C0C0C0")])
    _save(fig, "D12_observability")


# ═══════════════════════════════════════════════════════════════════════════════
# D13 FRONTEND ARCHITECTURE
# ═══════════════════════════════════════════════════════════════════════════════

def d13_frontend():
    fig, ax = _setup(16, 9, "D13 — Frontend Architecture",
                     "React 18 + TypeScript + Vite + Tailwind  |  Vercel static SPA")

    pages = [
        (0.10, 0.82, "/ Dashboard\nKPIs · Charts · Table\nTanStack Table", C["service"]),
        (0.10, 0.67, "/conversations/:id\nConversation Detail\nTranscript · QA · Ledger", C["service"]),
        (0.10, 0.52, "/admin\nAdmin Panel\nChecklist · Audit · Health", C["service"]),
        (0.10, 0.37, "/live-demo\nLive Demo\nScripted simulation", C["service"]),
        (0.10, 0.22, "/assistant\nAssistant Page\nChat · Sessions", C["service"]),
        (0.10, 0.08, "/login\nLogin Form\nJWT → localStorage", C["deterministic"]),
    ]
    for x, y, lbl, col in pages:
        _box(ax, x, y, 0.17, 0.09, lbl, color=col)

    infra = [
        (0.35, 0.85, "React Router v6\nclient-side routing\nSPA: no page reload", C["deterministic"]),
        (0.35, 0.70, "TanStack Query\nserver state\nfetch · cache · refetch", C["deterministic"]),
        (0.35, 0.55, "api.js\nall fetch wrappers\nATTACHES JWT header", C["deterministic"]),
        (0.35, 0.40, "App.jsx\nauth state\ntheme toggle\nroute guard", C["deterministic"]),
        (0.35, 0.25, "index.css\nCSS variables\nlight/dark tokens\nTailwind base", C["deterministic"]),
        (0.35, 0.10, "Recharts\nSVG charts\ntheme-aware colors", C["service"]),
    ]
    for x, y, lbl, col in infra:
        _box(ax, x, y, 0.17, 0.09, lbl, color=col)

    theme = [
        (0.60, 0.82, "Theme: Light (default)\n↔ Dark (toggle)\nCSS custom properties", C["deterministic"]),
        (0.60, 0.67, "Error handling\n401 → redirect login\n500 → error boundary\ncold-start spinner", C["gate"]),
        (0.60, 0.52, "Build: Vite\nbundle: dist/\nnginx.conf + vercel.json\nSPA fallback routing", C["service"]),
        (0.60, 0.37, "Auth state\nJWT in localStorage\n30 min expiry\nno refresh token", C["deterministic"]),
        (0.60, 0.22, "shadcn/ui + lucide\ncomponent library\naccessible primitives", C["service"]),
        (0.60, 0.08, "VITE_API_URL\npoints to Render\nbehind CORS allow-list", "#6A9A60"),
    ]
    for x, y, lbl, col in theme:
        _box(ax, x, y, 0.22, 0.09, lbl, color=col)

    known_issues = [
        (0.85, 0.80, "D20: Live Demo\nlacks provisional state\nand ledger update", C["gate"]),
        (0.85, 0.64, "D1: Resolution dist\nshows all 'unknown'\n(wrong DB join)", C["gate"]),
        (0.85, 0.49, "D23: Mock analyses\nin default dashboard", C["gate"]),
        (0.85, 0.35, "D21: Admin metrics\nonly token budget\nshown", C["gate"]),
    ]
    for x, y, lbl, col in known_issues:
        _box(ax, x, y, 0.22, 0.10, lbl, color=col)
    ax.text(0.85, 0.93, "Known UI bugs (Open)", ha="center",
            fontsize=8, fontweight="bold", color="red")

    ax.text(0.10, 0.97, "Pages / Routes", ha="center", fontsize=8.5, fontweight="bold")
    ax.text(0.35, 0.97, "Infrastructure", ha="center", fontsize=8.5, fontweight="bold")
    ax.text(0.60, 0.97, "Cross-cutting", ha="center", fontsize=8.5, fontweight="bold")

    caption = ("ADR-008: React + TypeScript + Vite (not Next.js: no SSR needed for dashboard).\n"
               "No refresh token: users re-login after 30 min (known limitation).\n"
               "Red boxes: open bugs from docs/bug-report.md.")
    ax.text(0.01, 0.0, caption, fontsize=7.5, color="#333")
    _legend(ax, [("Service", C["service"]), ("Logic", C["deterministic"]),
                 ("Known bug", C["gate"]), ("Config", "#6A9A60")])
    _save(fig, "D13_frontend")


# ═══════════════════════════════════════════════════════════════════════════════
# D14 OPTIONAL LAYERS
# ═══════════════════════════════════════════════════════════════════════════════

def d14_optional_layers():
    fig, ax = _setup(16, 9, "D14 — Optional & Add-on Layers",
                     "Action Layer · Assistant · Cases · Checklist manager  |  All attach to core read-only or via DB")

    core = [
        (0.15, 0.60, "Core Pipeline\n(conversations · turns\nanalyses · qa_results\ncommitments)", C["service"]),
        (0.15, 0.38, "PostgreSQL\n20 tables\nshared data layer", C["store"]),
    ]
    for x, y, lbl, col in core:
        _box(ax, x, y, 0.24, 0.14, lbl, color=col)
    ax.text(0.15, 0.80, "Core (always on)", ha="center", fontsize=8.5, fontweight="bold")

    layers = [
        # (x, y, name, description, flag, status)
        (0.45, 0.85, "Action Layer",
         "risk_engine · derive_job\nPDCA · recurrence\nplaybook · prevention",
         "ACTION_LAYER_ENABLED=false", "flagged-off"),
        (0.45, 0.62, "Chat Assistant",
         "tool-calling pipeline\n5 tool rounds max\nread-only DB access\nasst_session · asst_message",
         "No flag — always on", "implemented"),
        (0.45, 0.40, "Cases",
         "case + case_conversations\ncreate · link · list\nno detail view (D22)",
         "No flag — always on", "partial"),
        (0.45, 0.20, "Checklist Manager",
         "qa_checklist versioning\nYAML → DB seed\nadmin UI (D17 bug: 0 items shown)",
         "No flag — always on", "partial"),
    ]
    col_map = {"flagged-off": C["optional"], "implemented": C["service"], "partial": "#E07B39"}
    for x, y, name, desc, flag, status in layers:
        col = col_map[status]
        is_opt = status == "flagged-off"
        _box(ax, x, y, 0.26, 0.14, f"{name}\n{desc}", color=col,
             text_color=C["text_light"] if col != C["optional"] else "#333",
             linestyle="--" if is_opt else "-")
        ax.text(x + 0.13, y + 0.08, f"[{flag}]", fontsize=5.5, color="#555",
                ha="right", va="center")
        ax.text(x + 0.13, y + 0.05, f"status: {status}", fontsize=5.5,
                color={"flagged-off": "#808080", "implemented": "#2E75B6",
                       "partial": "#E07B39"}[status],
                ha="right", fontweight="bold")

    for x, y, name, desc, flag, status in layers:
        _arrow(ax, 0.27, 0.60, x - 0.13, y + 0.01, "reads DB", color="#888",
               linestyle="--" if status == "flagged-off" else "-")

    ax.text(0.45, 0.97, "Optional / Add-on Layers", ha="center",
            fontsize=8.5, fontweight="bold")

    # Read-only note for assistant
    ax.text(0.73, 0.70,
            "Assistant is READ-ONLY:\ntool_executor.py makes no\nwrite DB operations.\n"
            "Sessions in asst_session.",
            fontsize=7.5, color="#333",
            bbox=dict(facecolor="#EBF5FB", edgecolor="#2E75B6", pad=3))

    caption = ("Dashed border = feature-flagged off in current deployment (ACTION_LAYER_ENABLED=false).\n"
               "Orange = partial: implemented but has known open bugs (D17 checklist, D22 cases).\n"
               "All optional layers attach to the core via DB reads only (no core code changes needed).")
    ax.text(0.01, 0.01, caption, fontsize=7.5, color="#333")
    _legend(ax, [("Implemented", C["service"]), ("Partial (bugs open)", "#E07B39"),
                 ("Flagged-off", C["optional"])])
    _save(fig, "D14_optional_layers")


# ═══════════════════════════════════════════════════════════════════════════════
# D15 SCALE-OUT TARGET (design, not implemented)
# ═══════════════════════════════════════════════════════════════════════════════

def d15_scale_out():
    fig, axes = plt.subplots(1, 2, figsize=(20, 10))
    fig.patch.set_facecolor(C["bg"])

    for ax in axes:
        ax.set_facecolor(C["bg"])
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")

    # LEFT: current state
    ax = axes[0]
    ax.set_title("CURRENT ARCHITECTURE\n(implemented, code frozen)", fontsize=11,
                 fontweight="bold", color=C["text_dark"])

    current = [
        (0.50, 0.88, "Vercel\nStatic React SPA", C["service"]),
        (0.50, 0.72, "Render.com\nSingle Docker instance\nAPI + in-process rate limit", C["deterministic"]),
        (0.50, 0.55, "Worker process\nSame instance\npoll every 5s", C["deterministic"]),
        (0.50, 0.38, "Render PostgreSQL\nManaged free tier\nSingle DB", C["store"]),
        (0.50, 0.22, "In-process token budget\nIn-process rate limiter\n(not shared)", C["gate"]),
        (0.50, 0.08, "Groq/OpenRouter\nExternal LLM API", C["external"]),
    ]
    limits = [
        "✗ No horizontal scaling",
        "✗ Budget resets on restart",
        "✗ Rate limiter not distributed",
        "✗ Single point of failure",
        "✗ Cold start 30-60s",
        "✗ No persistent storage on Render FS",
    ]
    for x, y, lbl, col in current:
        _box(ax, x, y, 0.80, 0.10, lbl, color=col)
    for i, lbl in enumerate(limits):
        ax.text(0.05, 0.85 - i * 0.12, lbl, fontsize=7.5, color="red")

    # RIGHT: scale-out target
    ax = axes[1]
    ax.set_title("⚠  SCALE-OUT TARGET  ⚠\n(design only — NOT IMPLEMENTED)", fontsize=11,
                 fontweight="bold", color="red")

    target = [
        (0.50, 0.93, "CDN\nStatic assets cached globally", C["service"]),
        (0.50, 0.81, "Load Balancer\nnginx / AWS ALB / Cloudflare\nsticky sessions optional", C["service"]),
        (0.50, 0.68, "API replicas (N)\nstateless · horizontal scale\nDocker Swarm / k8s", C["deterministic"]),
        (0.50, 0.55, "Celery workers (M)\n+ Redis broker\npriority queues · retries", C["llm"]),
        (0.50, 0.42, "Redis\ntoken budget · rate limit\nsession cache", C["gate"]),
        (0.50, 0.29, "PostgreSQL (primary)\n+ read replicas\nConnection pool: PgBouncer", C["store"]),
        (0.50, 0.16, "Object storage (S3/GCS)\ndemo seeds · exports\nno ephemeral FS", "#6A9A60"),
        (0.50, 0.05, "Central logging (Grafana Cloud)\nSecrets manager (Vault/AWS SM)", "#808080"),
    ]
    for x, y, lbl, col in target:
        _box(ax, x, y, 0.80, 0.09, lbl, color=col,
             linestyle="--", alpha=0.7, lw=1.0)

    migration_steps = [
        "1. Move token budget + rate limiter → Redis",
        "2. Replace jobs table worker → Celery + Redis",
        "3. Add PostgreSQL read replicas + PgBouncer",
        "4. Move secrets → secrets manager",
        "5. Add load balancer + run N API replicas",
        "6. Move seeds/exports → object storage",
        "7. Connect Prometheus → Grafana Cloud",
    ]
    for i, step in enumerate(migration_steps):
        ax.text(0.02, 0.93 - i * 0.06, step, fontsize=7, color="#444")

    fig.suptitle("D15 — Scale-Out Design  |  Left = current  |  Right = target (dashed = NOT implemented)",
                 fontsize=11, fontweight="bold", color="red", y=0.99)

    svg_path = OUT_DIR / "D15_scale_out.svg"
    png_path = OUT_DIR / "D15_scale_out.png"
    fig.savefig(str(svg_path), format="svg", bbox_inches="tight", facecolor=fig.get_facecolor())
    fig.savefig(str(png_path), format="png", dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print("  Saved D15_scale_out.svg  D15_scale_out.png")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("EchoInsight Architecture Diagram Generator")
    print("=" * 50)
    funcs = [
        d0_master_poster, d1_system_context, d2_runtime_containers,
        d3_backend_components, d4_pipeline, d5_state_machine,
        d6_commitment, d7_qa_scoring, d8_sequence, d9_data_model,
        d10_security, d11_deployment, d12_observability, d13_frontend,
        d14_optional_layers, d15_scale_out,
    ]
    for fn in funcs:
        print(f"\n[{fn.__name__}]")
        try:
            fn()
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback; traceback.print_exc()
    print("\n" + "=" * 50)
    print(f"Done. Output: {OUT_DIR}")
    svgs = list(OUT_DIR.glob("*.svg"))
    pngs = list(OUT_DIR.glob("*.png"))
    print(f"  SVG files: {len(svgs)}")
    print(f"  PNG files: {len(pngs)}")
    for f in sorted(svgs):
        size = os.path.getsize(str(f))
        print(f"  {f.name}  ({size:,} bytes)")
