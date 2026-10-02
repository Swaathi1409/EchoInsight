#!/usr/bin/env bash
# seed_demo.sh - Import a sample of pool conversations and run batch analysis.
# Usage: bash scripts/seed_demo.sh [pool_size]
# Requires: GROQ_API_KEY, DATABASE_URL, the analysis pool manifest.
set -euo pipefail

POOL_SIZE="${1:-5}"
MANIFEST="data/manifests/analysis_pool_v1.json"

if [[ ! -f "${MANIFEST}" ]]; then
    echo "ERROR: Pool manifest not found at ${MANIFEST}" >&2
    echo "Run the data profiling script to create it first." >&2
    exit 1
fi

echo "Importing up to ${POOL_SIZE} conversations from pool manifest..."
python -c "
import json, os, sys, asyncio, httpx

manifest_path = '${MANIFEST}'
pool_size = int('${POOL_SIZE}')
api_base = os.environ.get('API_BASE_URL', 'http://localhost:8000')
admin_user = os.environ.get('DEMO_ADMIN_USER', 'admin')
admin_pass = os.environ.get('DEMO_ADMIN_PASS', 'admin123')

async def run():
    async with httpx.AsyncClient(base_url=api_base, timeout=60) as c:
        r = await c.post('/api/v1/auth/login', json={'username': admin_user, 'password': admin_pass})
        if r.status_code != 200:
            print(f'Login failed: {r.text}', file=sys.stderr)
            sys.exit(1)
        tok = r.json()['access_token']
        h = {'Authorization': f'Bearer {tok}'}

        with open(manifest_path) as f:
            pool = json.load(f)

        ids = pool.get('conversation_ids', [])[:pool_size]
        print(f'Submitting {len(ids)} conversations for analysis...')
        for cid in ids:
            r2 = await c.post('/api/v1/conversations/submit',
                json={'source_id': cid, 'channel': 'call', 'turns': [], 'metadata': {}},
                headers=h)
            if r2.status_code not in (200, 201, 202):
                print(f'  WARN: {cid} -> {r2.status_code}: {r2.text[:80]}')
            else:
                print(f'  OK: {cid} -> job {r2.json().get(\"job_id\", \"?\")}')

asyncio.run(run())
"

echo "Seed demo complete. Jobs queued for background worker processing."
echo "Start the worker to process: python -m backend.worker.main"
