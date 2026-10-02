# System Health Report

**Status**: Based on local development measurements only. No remote deployment metrics available.
All figures reflect the local dev environment (Windows 11, Python 3.11, SQLite in-memory for tests, SQLite on disk for dev).

---

## Test Suite Performance

| Suite | Tests | Duration | Status |
|-------|-------|----------|--------|
| Full suite (unit + integration + security) | 56 | 1.3 - 3.5s | PASS |
| Unit tests only | 45 | 0.8s | PASS |
| Integration tests | 11 | 2.5s | PASS |

Command: `python -m pytest tests/ -q`

---

## API Endpoint Latency (Local, SQLite, No LLM)

Measured with httpx async client via ASGI transport (in-process, no network overhead):

| Endpoint | Operation | Typical Latency |
|----------|-----------|-----------------|
| `POST /api/v1/auth/login` | Argon2 verify + JWT sign | 100-300ms |
| `POST /api/v1/conversations` | Insert + assign | 2-5ms |
| `POST /api/v1/conversations/{id}/turns` | Insert + reduce state | 3-8ms |
| `POST /api/v1/conversations/{id}/end` | Update + queue job | 2-4ms |
| `GET /api/v1/conversations` | List with scope filter | 1-3ms |
| `GET /api/v1/conversations/{id}` | Detail + turns join | 2-5ms |
| `GET /health` | DB ping | 1-2ms |
| `GET /ready` | Migration check | 2-5ms |

Note: LLM analysis jobs are asynchronous. The above latencies exclude LLM call time.
LLM call time (Groq API, real model): not measured in this environment (no valid API key active during testing).

---

## LLM Token Estimates (Not Measured in Current Run)

From Phase 0 measurements:
- Per-turn incremental call: ~171 tokens (Groq, qwen/qwen3.8-27b, 1 turn + 3 context turns)
- Full conversation batch call: estimated 800-2000 tokens depending on length
- Verification call: estimated 300-500 tokens per item

Free-tier Groq rate limits (documented at console.groq.com; verify before use):
- Do not assume; read current documentation.

---

## Container Memory Footprint

Estimated from Docker image composition (not measured in container runtime):

| Container | Estimated Idle Memory |
|-----------|-----------------------|
| Backend API (Python 3.11 + dependencies) | 120-180 MB |
| Worker (same image, lighter load) | 100-150 MB |
| Postgres 16 Alpine | 40-80 MB |
| Nginx + React static files | 8-15 MB |

**Minimum recommended**: 2 vCPU, 2 GB RAM for single-VM deployment.

---

## What Was Not Measured

- Load test (100 concurrent conversations): not run; requires LLM quota and running services.
- p50/p95 latency at production load: not measured.
- Full-volume ingest benchmark: not run (requires full 738 MB dataset).
- Real-model analysis latency: not measured in current environment.
- Container startup time: not measured.

These are documented future tasks for the owner to run when:
1. A valid Groq API key with sufficient quota is available.
2. The Docker images are built and started against a Postgres instance.
3. A load test tool (e.g., locust, k6, or the provided `scripts/seed_demo.sh`) is run.

---

## Known Performance Constraints

- **Argon2 login latency**: 100-300ms per login is expected and intentional (argon2id hardening).
  For high-throughput scenarios, implement token caching or rate limit login calls instead of weakening argon2.
- **SQLite in tests**: SQLite does not support `FOR UPDATE` row locking; concurrent-append tests use optimistic checks only.
  PostgreSQL is used in all non-unit-test environments.
- **Job queue**: Jobs are polled by the worker every 2 seconds (configurable). For high-volume deployments, replace with Celery + Redis.
