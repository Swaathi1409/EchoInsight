"""
Test: Leakage check.

Verifies that no gold test IDs appear in any:
- Prompt template files
- Fixture files
- Few-shot example files
- Threshold calibration files

This test must pass for CI to succeed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
GOLD_SPLIT_FILE = REPO_ROOT / "data" / "manifests" / "gold_split_v1.json"

# Directories and file patterns to scan for test ID leakage
SCAN_PATHS = [
    REPO_ROOT / "backend" / "llm",      # prompt templates
    REPO_ROOT / "backend" / "analysis",  # prompt templates
    REPO_ROOT / "backend" / "qa",        # fixtures
    REPO_ROOT / "tests" / "fixtures",    # hand-written test fixtures
    REPO_ROOT / "evals",                  # eval fixtures and calibration files
]
SCAN_EXTENSIONS = {".py", ".yaml", ".yml", ".json", ".txt", ".md"}


def load_test_ids() -> list[str]:
    """Load test conversation IDs from the gold split manifest."""
    if not GOLD_SPLIT_FILE.exists():
        pytest.skip(f"Gold split manifest not found: {GOLD_SPLIT_FILE}")
    with open(GOLD_SPLIT_FILE) as f:
        manifest = json.load(f)
    return manifest.get("test_ids", [])


def get_files_to_scan() -> list[Path]:
    """Collect all files to scan for test ID leakage."""
    files = []
    for scan_path in SCAN_PATHS:
        if not scan_path.exists():
            continue
        if scan_path.is_file():
            files.append(scan_path)
        else:
            for ext in SCAN_EXTENSIONS:
                files.extend(scan_path.rglob(f"*{ext}"))
    return files


def test_no_test_ids_in_prompt_files() -> None:
    """Verify that no gold test IDs appear in prompt templates, fixtures, or calibration files."""
    test_ids = load_test_ids()
    if not test_ids:
        pytest.skip("No test IDs in gold split manifest")

    files_to_scan = get_files_to_scan()
    violations: list[tuple[str, str, str]] = []

    for filepath in files_to_scan:
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
            for test_id in test_ids:
                if test_id in content:
                    violations.append((str(filepath.relative_to(REPO_ROOT)), test_id[:12] + "...", "found in file"))
        except OSError:
            continue

    if violations:
        violation_text = "\n".join(f"  {path}: {tid}" for path, tid, _ in violations)
        pytest.fail(
            f"LEAKAGE DETECTED: {len(violations)} test ID(s) found in prompt/fixture/calibration files.\n"
            f"Test IDs must NEVER appear in these files.\n"
            f"Violations:\n{violation_text}\n\n"
            f"See data/manifests/gold_split_v1.json for the test ID list.\n"
            f"Remove these IDs from the listed files before committing."
        )


def test_gold_split_manifest_exists() -> None:
    """Verify the gold split manifest file exists and has expected structure."""
    assert GOLD_SPLIT_FILE.exists(), f"Gold split manifest not found: {GOLD_SPLIT_FILE}"
    with open(GOLD_SPLIT_FILE) as f:
        manifest = json.load(f)
    assert "dev_ids" in manifest, "Gold split manifest missing dev_ids"
    assert "test_ids" in manifest, "Gold split manifest missing test_ids"
    assert len(manifest["dev_ids"]) > 0, "Gold split manifest has empty dev_ids"
    assert len(manifest["test_ids"]) > 0, "Gold split manifest has empty test_ids"
    # Dev and test sets must be disjoint
    dev_set = set(manifest["dev_ids"])
    test_set = set(manifest["test_ids"])
    overlap = dev_set & test_set
    assert not overlap, f"Dev and test sets overlap: {len(overlap)} IDs in both"


def test_pool_manifest_exists() -> None:
    """Verify the analysis pool manifest exists and is consistent."""
    pool_file = REPO_ROOT / "data" / "manifests" / "analysis_pool_v1.json"
    assert pool_file.exists(), f"Pool manifest not found: {pool_file}"
    with open(pool_file) as f:
        manifest = json.load(f)
    assert "conversation_ids" in manifest
    assert manifest["pool_size"] == len(manifest["conversation_ids"]), (
        "pool_size field does not match actual list length"
    )
    assert manifest["seed"] == 42
    assert manifest["dataset_revision"] == "c8bfc7797a347b493f65fdc4e4c9694a8a19b56f"


def test_test_ids_not_in_pool_sample() -> None:
    """Verify that if a data/sample/ directory exists, it contains no test IDs."""
    sample_dir = REPO_ROOT / "data" / "sample"
    if not sample_dir.exists():
        return  # No sample directory is fine

    test_ids = load_test_ids()
    test_id_set = set(test_ids)

    for filepath in sample_dir.rglob("*.json"):
        try:
            content = filepath.read_text()
            for test_id in test_id_set:
                if test_id in content:
                    pytest.fail(
                        f"Test ID found in sample file: {filepath.relative_to(REPO_ROOT)}. "
                        f"Sample files must never contain test IDs."
                    )
        except OSError:
            continue
