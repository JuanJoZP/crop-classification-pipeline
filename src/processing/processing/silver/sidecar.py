import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def build_sidecar(
    bronze_sidecar: dict, processing_timestamp: str, git_sha: str
) -> dict:
    silver_metadata = {
        "git_sha": git_sha,
        "processing_step": "silver",
        "timestamp": processing_timestamp,
    }

    sidecar = dict(bronze_sidecar)
    sidecar["processing_silver_metadata"] = silver_metadata
    return sidecar


def should_process(
    bronze_sidecar: dict,
    silver_sidecar: dict | None,
    current_git_sha: str,
) -> bool:
    if silver_sidecar is None:
        return True

    silver_meta = silver_sidecar.get("processing_silver_metadata", {})
    bronze_git_sha = bronze_sidecar.get("processing_bronze_metadata", {}).get(
        "git_sha", ""
    )
    silver_bronze_git_sha = silver_sidecar.get("processing_bronze_metadata", {}).get(
        "git_sha", ""
    )

    if silver_meta.get("git_sha") != current_git_sha:
        return True

    if bronze_git_sha != silver_bronze_git_sha:
        return True

    return False