import json
import logging
from datetime import datetime, timezone

import boto3

S3_BUCKET = None
OUTPUT_PREFIX = None

s3_client = None
logger = logging.getLogger(__name__)


def init(bucket: str, output_prefix: str):
    global S3_BUCKET, OUTPUT_PREFIX, s3_client
    S3_BUCKET = bucket
    OUTPUT_PREFIX = output_prefix
    s3_client = boto3.client("s3")


def discover_silver_parcels(processed_prefix: str) -> list[str]:
    logger.info("Discovering silver sidecars in s3://%s/%s/", S3_BUCKET, processed_prefix)
    paginator = s3_client.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=S3_BUCKET, Prefix=f"{processed_prefix}/")

    keys = []
    for page in pages:
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith("_metadata.json") and f"{processed_prefix}/" in key:
                keys.append(key)

    logger.info("Found %d silver sidecars", len(keys))
    return keys


def load_silver_sidecar(key: str) -> dict:
    response = s3_client.get_object(Bucket=S3_BUCKET, Key=key)
    return json.loads(response["Body"].read().decode("utf-8"))


def load_gold_metadata() -> dict | None:
    key = f"{OUTPUT_PREFIX}/metadata.json"
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=key)
        return json.loads(response["Body"].read().decode("utf-8"))
    except s3_client.exceptions.NoSuchKey:
        return None


def upload_file(local_path: str, s3_key: str):
    s3_client.upload_file(local_path, S3_BUCKET, s3_key)
    logger.info("Uploaded to s3://%s/%s", S3_BUCKET, s3_key)


def list_existing_parquets() -> list[str]:
    paginator = s3_client.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=S3_BUCKET, Prefix=f"{OUTPUT_PREFIX}/")
    keys = []
    for page in pages:
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.startswith(f"{OUTPUT_PREFIX}/gold_timeseries_") and key.endswith(".parquet"):
                keys.append(key)
    return keys