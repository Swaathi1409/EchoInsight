"""
Fetch conversations from the HuggingFace datasets-server API.

This script reconstructs local conversation data from the analysis pool manifest
without downloading the full corpus. Use this for local development and testing.

Usage:
    python -m data.scripts.fetch_conversations
    python -m data.scripts.fetch_conversations --conversation-id <id>
    python -m data.scripts.fetch_conversations --pool-only  # fetch all pool conversations
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

HF_API_BASE = "https://datasets-server.huggingface.co"
DATASET = "talkmap/telecom-conversation-corpus"
CONFIG = "default"
SPLIT = "train"

# Paths relative to repo root
REPO_ROOT = Path(__file__).parent.parent.parent
POOL_MANIFEST = REPO_ROOT / "data" / "manifests" / "analysis_pool_v1.json"
DATA_CACHE_DIR = REPO_ROOT / "data" / "raw"  # local only, in .gitignore


def fetch_rows(offset: int, length: int = 100, retries: int = 3) -> list[dict[str, Any]]:
    """Fetch rows from the HuggingFace datasets-server API."""
    url = (
        f"{HF_API_BASE}/rows"
        f"?dataset={DATASET}&config={CONFIG}&split={SPLIT}"
        f"&offset={offset}&length={length}"
    )
    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=60)
            if resp.ok:
                return resp.json().get("rows", [])
            if resp.status_code in (429, 502, 503):
                wait = 2 ** attempt
                logger.warning("Rate limited or server error at offset %d. Waiting %ds.", offset, wait)
                time.sleep(wait)
                continue
            logger.error("Failed to fetch rows at offset %d: %d %s", offset, resp.status_code, resp.text[:200])
            return []
        except requests.RequestException as exc:
            logger.error("Request error at offset %d: %s", offset, exc)
            time.sleep(2 ** attempt)
    return []


def fetch_conversation(conversation_id: str) -> list[dict[str, Any]]:
    """
    Fetch all turns for a given conversation_id.

    This is a best-effort function. The HuggingFace API does not support filtering
    by conversation_id, so this searches by scanning known offsets from the pool manifest.

    Returns a list of turn dicts sorted by date_time, or empty list if not found.
    """
    cache_file = DATA_CACHE_DIR / f"{conversation_id}.json"
    if cache_file.exists():
        with open(cache_file) as f:
            return json.load(f)

    # Search pool manifest for offset hint
    if POOL_MANIFEST.exists():
        with open(POOL_MANIFEST) as f:
            manifest = json.load(f)
        features = manifest.get("conversation_features", [])
        for feat in features:
            if feat.get("conversation_id") == conversation_id:
                # We don't store the offset in the manifest; do a scan
                break

    # Scan offsets to find conversation (brute-force, acceptable for small pools)
    # In production, conversations are stored in the database after first fetch
    logger.info("Searching for conversation %s via HF API scan...", conversation_id[:12])
    turns = []
    for offset in range(0, 3726699, 50000):
        rows = fetch_rows(offset, length=100)
        conv_rows = [r["row"] for r in rows if r["row"]["conversation_id"] == conversation_id]
        if conv_rows:
            # Fetch a wider block to get the complete conversation
            wider = fetch_rows(max(0, offset - 50), length=200)
            turns = [r["row"] for r in wider if r["row"]["conversation_id"] == conversation_id]
            break

    if turns:
        turns.sort(key=lambda t: t["date_time"])
        DATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(cache_file, "w") as f:
            json.dump(turns, f)
        logger.info("Cached %d turns for %s", len(turns), conversation_id[:12])

    return turns


def fetch_pool_conversations() -> dict[str, list[dict[str, Any]]]:
    """Fetch all conversations in the analysis pool from the HF API."""
    if not POOL_MANIFEST.exists():
        raise FileNotFoundError(f"Pool manifest not found: {POOL_MANIFEST}")

    with open(POOL_MANIFEST) as f:
        manifest = json.load(f)

    pool_ids = manifest["conversation_ids"]
    logger.info("Fetching %d pool conversations...", len(pool_ids))

    result: dict[str, list[dict[str, Any]]] = {}
    for i, conv_id in enumerate(pool_ids):
        turns = fetch_conversation(conv_id)
        result[conv_id] = turns
        if (i + 1) % 10 == 0:
            logger.info("Fetched %d / %d conversations", i + 1, len(pool_ids))

    return result


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Fetch telecom conversations from HuggingFace")
    parser.add_argument("--conversation-id", help="Fetch a specific conversation by ID")
    parser.add_argument("--pool-only", action="store_true", help="Fetch all pool conversations")
    args = parser.parse_args()

    if args.conversation_id:
        turns = fetch_conversation(args.conversation_id)
        if turns:
            print(f"Fetched {len(turns)} turns for {args.conversation_id[:12]}")
            for t in turns:
                print(f"  [{t['speaker']:6}] {t['text'][:80]!r}")
        else:
            print(f"Conversation {args.conversation_id} not found")
    elif args.pool_only:
        result = fetch_pool_conversations()
        print(f"Fetched {len(result)} conversations. Cached to {DATA_CACHE_DIR}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
