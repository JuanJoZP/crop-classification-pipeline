import json
import os
from datetime import datetime, timezone
from typing import Any, Dict

import boto3

from client import SUPPORTED_CROPS, fetch_municipalities

S3_BUCKET = os.environ["S3_BUCKET"]
S3_PREFIX = os.environ.get("S3_PREFIX", "polygons")
s3_client = boto3.client("s3")


def _upload_to_s3(data: bytes, key: str, metadata: Dict[str, str]) -> str:
    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=data,
        ContentType="application/json",
        Metadata=metadata,
    )
    return key


def handle(event: Dict[str, Any]) -> Dict[str, Any]:
    crop = event.get("crop") or event.get("body", {}).get("crop") or ""
    crop = str(crop).strip()

    if not crop:
        return {
            "statusCode": 400,
            "body": json.dumps(
                {"error": "crop is required", "supported_crops": SUPPORTED_CROPS}
            ),
        }

    if crop.lower() not in [c.lower() for c in SUPPORTED_CROPS]:
        return {
            "statusCode": 400,
            "body": json.dumps(
                {
                    "error": f"Unsupported crop: '{crop}'.",
                    "supported_crops": SUPPORTED_CROPS,
                }
            ),
        }

    municipalities = fetch_municipalities(crop)

    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%dT%H%M%SZ")
    key = f"{S3_PREFIX}/list_municipalities_{timestamp}.json"

    payload = {
        "crop": crop,
        "count": len(municipalities),
        "municipalities": municipalities,
    }

    metadata = {
        "action": "list_municipalities",
        "crop": crop,
        "timestamp": timestamp,
    }

    s3_key = _upload_to_s3(
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        key=key,
        metadata=metadata,
    )

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "s3_key": s3_key,
                "crop": crop,
                "count": len(municipalities),
                "timestamp": timestamp,
            }
        ),
    }
