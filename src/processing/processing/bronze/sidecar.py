import logging

from shapely.geometry import mapping

logger = logging.getLogger(__name__)


def polygon_id(row) -> str:
    return f"{row['service']}_{row['objectid']}"


def build_sidecar(
    row, processing_timestamp: str, git_sha: str, polygons_key: str
) -> dict:
    props = row.to_dict()
    props["geometry"] = mapping(props["geometry"])
    return {
        "properties": props,
        "processing_bronze_metadata": {
            "git_sha": git_sha,
            "processing_step": "bronze",
            "timestamp": processing_timestamp,
            "polygons_key": polygons_key,
        },
    }
