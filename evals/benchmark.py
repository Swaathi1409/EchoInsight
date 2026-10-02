"""
Full-volume ingest benchmark.

Measures p50/p95/p99 append-turn latency under load.
Sends N concurrent conversations with M turns each.

Usage:
    python evals/benchmark.py --conversations 50 --turns 10 --url http://localhost:8000

Output: benchmark_results/bench_<timestamp>.json
"""
from __future__ import annotations
import argparse
import asyncio
import json
import logging
import statistics
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

RESULTS_DIR = Path(__file__).parent / "benchmark_results"

SAMPLE_TURNS = [
    ("agent", "Thank you for calling TelecomCorp, my name is Alex. How can I help you today?"),
    ("customer", "Hi, I've been having issues with my internet connection. It keeps dropping every few hours."),
    ("agent", "I'm sorry to hear that. Can I please verify your account with your date of birth?"),
    ("customer", "Sure, it's the 15th of March 1985."),
    ("agent", "Thank you. I can see you're on our Fiber 200 plan. Let me run a diagnostic on your line."),
    ("customer", "How long will that take?"),
    ("agent", "Just a couple of minutes. I can see some instability on the signal. I'll escalate this to our technical team."),
    ("customer", "Will this be fixed today? I work from home and it's really affecting my work."),
    ("agent", "I understand how important this is. I'll create a priority ticket for you. You should hear back within 4 hours."),
    ("customer", "That's fine. Will you follow up with me personally?"),
]


async def _login(client: httpx.AsyncClient, url: str, username: str, password: str) -> str:
    r = await client.post(f"{url}/api/v1/auth/login", json={"username": username, "password": password})
    r.raise_for_status()
    return r.json()["access_token"]


async def _bench_conversation(
    client: httpx.AsyncClient,
    url: str,
    token: str,
    n_turns: int,
) -> dict:
    """Create one conversation, append n_turns, end it. Return timing data."""
    headers = {"Authorization": f"Bearer {token}"}
    turn_latencies: list[float] = []

    # Create
    r = await client.post(f"{url}/api/v1/conversations",
                          json={"channel": "call"}, headers=headers)
    if r.status_code not in (200, 201):
        return {"error": f"create failed: {r.status_code}"}
    conv_id = r.json()["id"]

    # Append turns
    for i in range(n_turns):
        sp, txt = SAMPLE_TURNS[i % len(SAMPLE_TURNS)]
        ikey = f"bench-{conv_id}-{i}-{uuid.uuid4()}"
        t0 = time.perf_counter()
        r = await client.post(
            f"{url}/api/v1/conversations/{conv_id}/turns",
            json={"speaker": sp, "text": txt, "idempotency_key": ikey},
            headers=headers,
        )
        latency = (time.perf_counter() - t0) * 1000
        turn_latencies.append(latency)
        if r.status_code not in (200, 201):
            logger.warning("Turn %d failed: %s %s", i, r.status_code, r.text[:80])

    # End
    await client.post(f"{url}/api/v1/conversations/{conv_id}/end", headers=headers)

    return {
        "conversation_id": conv_id,
        "turns": n_turns,
        "turn_latencies_ms": turn_latencies,
        "p50_ms": statistics.median(turn_latencies) if turn_latencies else None,
        "p95_ms": sorted(turn_latencies)[int(len(turn_latencies) * 0.95)] if turn_latencies else None,
        "total_ms": sum(turn_latencies),
    }


async def run_benchmark(url: str, n_conversations: int, n_turns: int, concurrency: int,
                        username: str, password: str) -> dict:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    logger.info("Benchmark: %d conversations x %d turns, concurrency=%d, url=%s",
                n_conversations, n_turns, concurrency, url)

    async with httpx.AsyncClient(timeout=60) as client:
        token = await _login(client, url, username, password)

        sem = asyncio.Semaphore(concurrency)

        async def bounded(i: int):
            async with sem:
                logger.info("  conv %d/%d", i + 1, n_conversations)
                return await _bench_conversation(client, url, token, n_turns)

        wall_start = time.perf_counter()
        results = await asyncio.gather(*[bounded(i) for i in range(n_conversations)])
        wall_seconds = time.perf_counter() - wall_start

    all_latencies = [l for r in results if "turn_latencies_ms" in r for l in r["turn_latencies_ms"]]
    errors = [r for r in results if "error" in r]

    def _p(pct):
        if not all_latencies:
            return None
        return round(sorted(all_latencies)[int(len(all_latencies) * pct / 100)], 1)

    report = {
        "timestamp": timestamp,
        "config": {"url": url, "conversations": n_conversations, "turns_per_conv": n_turns, "concurrency": concurrency},
        "wall_seconds": round(wall_seconds, 2),
        "total_turns": len(all_latencies),
        "turns_per_second": round(len(all_latencies) / wall_seconds, 1) if wall_seconds else 0,
        "error_count": len(errors),
        "latency_ms": {
            "p50": _p(50),
            "p75": _p(75),
            "p95": _p(95),
            "p99": _p(99),
            "max": round(max(all_latencies), 1) if all_latencies else None,
            "min": round(min(all_latencies), 1) if all_latencies else None,
        },
        "errors": errors[:10],
    }

    out = RESULTS_DIR / f"bench_{timestamp}.json"
    with out.open("w") as f:
        json.dump(report, f, indent=2)

    logger.info("Benchmark complete:")
    logger.info("  Wall time: %.1fs | Throughput: %.1f turns/s", wall_seconds, report["turns_per_second"])
    logger.info("  p50=%.1fms p95=%.1fms p99=%.1fms", _p(50) or 0, _p(95) or 0, _p(99) or 0)
    logger.info("  Errors: %d / %d conversations", len(errors), n_conversations)
    logger.info("  Results: %s", out)
    return report


def main():
    parser = argparse.ArgumentParser(description="EchoInsight ingest benchmark")
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--conversations", type=int, default=20)
    parser.add_argument("--turns", type=int, default=10)
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="admin123")
    args = parser.parse_args()

    asyncio.run(run_benchmark(
        url=args.url,
        n_conversations=args.conversations,
        n_turns=args.turns,
        concurrency=args.concurrency,
        username=args.username,
        password=args.password,
    ))


if __name__ == "__main__":
    main()
