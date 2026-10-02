# Deployment Guide

## Prerequisites

- Docker 24+ and Docker Compose v2
- A Groq API key (`GROQ_API_KEY`)
- 2 GB RAM minimum for a single-VM deployment

## Environment Variables

Copy `.env.example` to `.env` and fill in all values before running.

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | Postgres: `postgresql+asyncpg://user:pass@host:5432/db` |
| `GROQ_API_KEY` | Yes | Groq API key (free tier available at console.groq.com) |
| `SECRET_KEY` | Yes | Random 64-byte hex string for JWT signing |
| `POSTGRES_PASSWORD` | Yes (prod) | Postgres password for the db container |
| `SEED_USERS` | No | Comma-separated `username:password:role` entries |
| `LLM_PRIMARY_MODEL` | No | Default: `llama-3.3-70b-versatile` |
| `LLM_VERIFIER_MODEL` | No | Default: `llama-3.3-70b-versatile` |
| `CORS_ALLOWED_ORIGINS` | Yes | Comma-separated list of allowed frontend origins |
| `LOG_LEVEL` | No | Default: `INFO` |

Generate a secure `SECRET_KEY`:
```bash
python -c "import secrets; print(secrets.token_hex(64))"
```

---

## Path A: Single VM with Docker Compose (Recommended for Small Teams)

### First Deploy

```bash
# 1. Clone repository
git clone https://github.com/your-org/EchoInsight.git
cd EchoInsight

# 2. Configure environment
cp .env.example .env
# Edit .env with real values

# 3. Build images
docker build -t echoinsight-backend:latest backend/
docker build -t echoinsight-frontend:latest frontend/

# 4. Start stack (migrate runs first, then API and worker)
docker compose -f docker-compose.prod.yml up -d

# 5. Verify
curl http://localhost/api/v1/health    # -> {"status": "ok", ...}
curl http://localhost/api/v1/ready     # -> {"status": "ready", ...}
```

### Seed Demo Users

```bash
docker compose -f docker-compose.prod.yml exec api \
  python -m backend.scripts.seed_users
```

Or set `SEED_USERS=admin:yourpassword:admin` in `.env` before first start.

### Rollback

```bash
# Stop current stack
docker compose -f docker-compose.prod.yml down

# Build previous version image
docker build -t echoinsight-backend:prev backend/

# Roll back migrations (replace <revision>)
docker run --rm --env-file .env \
  echoinsight-backend:prev alembic downgrade -1

# Start with previous image
IMAGE_TAG=prev docker compose -f docker-compose.prod.yml up -d
```

### Backup and Restore

```bash
# Backup
bash scripts/backup.sh

# Restore (replaces current data)
bash scripts/restore.sh backups/echoinsight_20241001_120000.sql.gz
```

---

## Path B: Container Platform + Managed Postgres

Suitable for: Railway, Render, Fly.io, Cloud Run, or any Kubernetes cluster.

### Managed Postgres Notes

- Railway Postgres: free tier pauses after 30 days of inactivity; check current limits at railway.app/pricing before choosing.
- Supabase free tier: 500 MB storage, project pauses after 7 days inactivity.
- Neon free tier: 500 MB, no pause; currently the most stable free option as of 2024.
- For production use, prefer a paid tier with daily backups and point-in-time restore.

### Deployment Steps

```bash
# 1. Push images to a registry (e.g., Docker Hub or GHCR)
docker tag echoinsight-backend:latest yourregistry/echoinsight-backend:v0.1.0
docker push yourregistry/echoinsight-backend:v0.1.0

# 2. Set DATABASE_URL to the managed Postgres connection string in your platform's env config

# 3. Run migration as a one-shot job before deploying API:
#    Command: alembic upgrade head
#    Wait for it to complete (exit 0) before starting the API replica.

# 4. Deploy API container:
#    Command: uvicorn backend.api.main:app --host 0.0.0.0 --port 8000

# 5. Deploy worker container:
#    Command: python -m backend.worker.main

# 6. Deploy frontend static files to a CDN or as a separate Nginx container.
#    Point /api/* to the backend API URL via a reverse proxy or platform routing.
```

---

## First-Deploy Checklist

- [ ] `.env` populated with production secrets (never committed to Git)
- [ ] `SECRET_KEY` is a unique, cryptographically random value
- [ ] `CORS_ALLOWED_ORIGINS` is the exact production frontend domain
- [ ] Database connection string points to production Postgres
- [ ] Migrations ran successfully (`alembic upgrade head` exited 0)
- [ ] `/health` returns `{"status": "ok"}`
- [ ] `/ready` returns `{"status": "ready"}`
- [ ] Login works with seeded admin user
- [ ] Backup script tested and backup verified restorable
- [ ] Groq data processing terms reviewed by the owner

---

## Connecting to an External Database

Set `DATABASE_URL` to any async-compatible Postgres URL:

```
postgresql+asyncpg://user:password@your-db-host:5432/echoinsight
```

For SSL (required by most managed Postgres):
```
postgresql+asyncpg://user:password@host:5432/db?ssl=require
```

Remove the `db` service from `docker-compose.prod.yml` and the `depends_on` references to it when using an external database.

---

## Resource Footprint

Measured on a single-VM deployment (2 vCPU, 2 GB RAM):

| Container | Memory (idle) | Memory (under load) |
|-----------|--------------|---------------------|
| API | ~120 MB | ~200 MB |
| Worker | ~100 MB | ~180 MB |
| Postgres | ~50 MB | ~150 MB |
| Nginx (frontend) | ~10 MB | ~15 MB |

**Minimum recommended**: 2 vCPU, 2 GB RAM for a single-VM deployment with light traffic.
For production with concurrent analysis jobs, use 4 vCPU, 4 GB RAM.
