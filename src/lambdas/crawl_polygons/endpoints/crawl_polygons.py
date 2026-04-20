import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

import boto3

from client import VALID_PERIODS, fetch_polygons, rows_to_geojson, validate_periods
from municipalities import validate_municipalities

S3_BUCKET = os.environ["S3_BUCKET"]
S3_PREFIX = os.environ.get("S3_PREFIX", "polygons")
GIT_SHA = os.environ.get("GIT_SHA", "unknown")
s3_client = boto3.client("s3")


def _parse_event(event: Dict[str, Any]) -> Tuple[List[str], List[str], int, int, int]:
    if isinstance(event.get("body"), str):
        body: Dict[str, Any] = json.loads(event["body"])
        municipios: List[str] = body.get("municipios", [])
        periodos: List[str] = body.get("periodos", [])
        limit: int = body.get("limit", 0)
        batch_size: int = body.get("batch_size", 0)
        silver_batch_size: int = body.get("silver_batch_size", 0)
    elif isinstance(event.get("body"), dict):
        municipios = event.get("municipios") or event["body"].get("municipios", [])
        periodos = event.get("periodos") or event["body"].get("periodos", [])
        limit = event.get("limit") or event["body"].get("limit", 0)
        batch_size = event.get("batch_size") or event["body"].get("batch_size", 0)
        silver_batch_size = event.get("silver_batch_size") or event["body"].get("silver_batch_size", 0)
    else:
        municipios = event.get("municipios", [])
        periodos = event.get("periodos", [])
        limit = event.get("limit", 0)
        batch_size = event.get("batch_size", 0)
        silver_batch_size = event.get("silver_batch_size", 0)
    return municipios, periodos, limit, batch_size, silver_batch_size


def _compute_batches(total: int, batch_size: int, s3_key: str, include_key: bool = True) -> List[Dict[str, Any]]:
    if batch_size <= 0:
        batch_size = total
    batches = []
    for offset in range(0, total, batch_size):
        remaining = total - offset
        size = min(batch_size, remaining)
        batch: Dict[str, Any] = {"offset": str(offset), "limit": str(size)}
        if include_key:
            batch["polygons_key"] = s3_key
        batches.append(batch)
    return batches


def _upload_to_s3(data: bytes, key: str, metadata: Dict[str, str]) -> str:
    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=data,
        ContentType="application/json",
        Metadata=metadata,
    )
    return key


def handle(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    municipios, periodos, limit, batch_size, silver_batch_size = _parse_event(event)

    if not municipios or not periodos:
        raise ValueError("municipios and periodos are required")

    invalid = validate_municipalities(municipios)
    if invalid:
        raise ValueError(
            f"Invalid municipalities: {invalid}. "
            f"See municipalities_papa.json for valid names."
        )

    invalid_periods = validate_periods(periodos)
    if invalid_periods:
        raise ValueError(
            f"Invalid periods: {invalid_periods}. "
            f"Valid periods: {sorted(VALID_PERIODS.keys())}."
        )

    rows = fetch_polygons(municipios, periodos)
    if limit and limit > 0:
        rows = rows[:limit]
    geojson = rows_to_geojson(rows)

    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%dT%H%M%SZ")
    key = f"{S3_PREFIX}/crawl_polygons_{timestamp}.json"

    metadata = {
        "action": "crawl_polygons",
        "municipios": json.dumps(municipios),
        "periodos": json.dumps(periodos),
        "timestamp": timestamp,
        "git_sha": GIT_SHA,
    }

    s3_key = _upload_to_s3(
        data=json.dumps(geojson, ensure_ascii=False).encode("utf-8"),
        key=key,
        metadata=metadata,
    )

    total_polygons = geojson["count"]
    bronze_batches = _compute_batches(total_polygons, batch_size, s3_key, include_key=True)
    silver_batches = _compute_batches(total_polygons, silver_batch_size, s3_key, include_key=False)
    gold_job_name = f"crop-gold-{timestamp}".lower()

    return {
        "s3_key": s3_key,
        "total_polygons": total_polygons,
        "municipios": municipios,
        "periodos": periodos,
        "timestamp": timestamp,
        "git_sha": GIT_SHA,
        "bronze_batches": bronze_batches,
        "silver_batches": silver_batches,
        "gold_job_name": gold_job_name,
    }
