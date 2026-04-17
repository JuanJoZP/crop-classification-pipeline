import logging

logger = logging.getLogger(__name__)


def polygon_id(row) -> str:
    return f"{row['service']}_{row['objectid']}"


def build_sidecar(
    row, processing_timestamp: str, git_sha: str, polygons_key: str
) -> dict:
    return {
        "properties": row.to_dict(),
        "processing_bronze_metadata": {
            "git_sha": git_sha,
            "processing_step": "bronze",
            "timestamp": processing_timestamp,
            "polygons_key": polygons_key,
        },
    }
