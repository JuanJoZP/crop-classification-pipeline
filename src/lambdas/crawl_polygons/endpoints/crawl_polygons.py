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


def _parse_event(event: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    if isinstance(event.get("body"), str):
        body: Dict[str, Any] = json.loads(event["body"])
        municipios: List[str] = body.get("municipios", [])
        periodos: List[str] = body.get("periodos", [])
    elif isinstance(event.get("body"), dict):
        municipios = event.get("municipios") or event["body"].get("municipios", [])
        periodos = event.get("periodos") or event["body"].get("periodos", [])
    else:
        municipios = event.get("municipios", [])
        periodos = event.get("periodos", [])
    return municipios, periodos


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
    municipios, periodos = _parse_event(event)

    if not municipios or not periodos:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "municipios and periodos are required"}),
        }

    invalid = validate_municipalities(municipios)
    if invalid:
        return {
            "statusCode": 400,
            "body": json.dumps(
                {
                    "error": f"Invalid municipalities: {invalid}. "
                    f"See municipalities_papa.json for valid names.",
                }
            ),
        }

    invalid_periods = validate_periods(periodos)
    if invalid_periods:
        return {
            "statusCode": 400,
            "body": json.dumps(
                {
                    "error": f"Invalid periods: {invalid_periods}. "
                    f"Valid periods: {sorted(VALID_PERIODS.keys())}.",
                }
            ),
        }

    rows = fetch_polygons(municipios, periodos)
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

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "s3_key": s3_key,
                "count": geojson["count"],
                "municipios": municipios,
                "periodos": periodos,
                "timestamp": timestamp,
                "git_sha": GIT_SHA,
            }
        ),
    }
