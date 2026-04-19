import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def build_sidecar(silver_sidecar: dict, processing_timestamp: str, git_sha: str) -> dict:
    gold_metadata = {
        "git_sha": git_sha,
        "processing_step": "gold",
        "timestamp": processing_timestamp,
    }

    sidecar = dict(silver_sidecar)
    sidecar["processing_gold_metadata"] = gold_metadata
    return sidecar


def should_process(
    silver_sidecar: dict,
    gold_sidecar: dict | None,
    current_git_sha: str,
) -> bool:
    if gold_sidecar is None:
        return True

    gold_meta = gold_sidecar.get("processing_gold_metadata", {})
    silver_git_sha = silver_sidecar.get("processing_silver_metadata", {}).get("git_sha", "")
    gold_silver_git_sha = gold_sidecar.get("processing_silver_metadata", {}).get("git_sha", "")

    if gold_meta.get("git_sha") != current_git_sha:
        return True

    if silver_git_sha != gold_silver_git_sha:
        return True

    return False