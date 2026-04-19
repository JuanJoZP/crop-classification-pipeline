import json
import logging
import os

import boto3
import s3fs
import xarray as xr

S3_BUCKET = os.environ["S3_BUCKET"]
RAW_PREFIX = os.environ.get("RAW_PREFIX", "raw")
PROCESSED_PREFIX = os.environ.get("PROCESSED_PREFIX", "processed")

s3_client = boto3.client("s3")

logger = logging.getLogger(__name__)


def discover_parcels() -> list[str]:
    logger.info("Discovering bronze sidecars in s3://%s/%s/", S3_BUCKET, RAW_PREFIX)
    paginator = s3_client.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=S3_BUCKET, Prefix=f"{RAW_PREFIX}/")

    sidecar_keys = []
    for page in pages:
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith("_metadata.json") and f"{RAW_PREFIX}/" in key:
                sidecar_keys.append(key)

    logger.info("Found %d bronze sidecars", len(sidecar_keys))
    return sidecar_keys


def load_bronze_sidecar(key: str) -> dict:
    response = s3_client.get_object(Bucket=S3_BUCKET, Key=key)
    body = response["Body"].read().decode("utf-8")
    return json.loads(body)


def load_silver_sidecar(pid: str) -> dict | None:
    key = f"{PROCESSED_PREFIX}/{pid}_metadata.json"
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=key)
        body = response["Body"].read().decode("utf-8")
        return json.loads(body)
    except s3_client.exceptions.NoSuchKey:
        return None


def load_zarr(pid: str, s3: s3fs.S3FileSystem) -> xr.Dataset:
    zarr_path = f"s3://{S3_BUCKET}/{RAW_PREFIX}/{pid}.zarr"
    logger.info("Loading zarr from %s", zarr_path)
    store = s3fs.S3Map(root=zarr_path, s3=s3, check=False)
    ds = xr.open_zarr(store, consolidated=True)
    return ds


def save_zarr(pid: str, dataset: xr.Dataset, s3: s3fs.S3FileSystem) -> str:
    zarr_path = f"s3://{S3_BUCKET}/{PROCESSED_PREFIX}/{pid}.zarr"
    logger.info("Saving zarr to %s", zarr_path)
    if s3.exists(zarr_path):
        s3.rm(zarr_path, recursive=True)
    store = s3fs.S3Map(root=zarr_path, s3=s3, check=False)
    dataset.to_zarr(store, consolidated=True)
    return f"{PROCESSED_PREFIX}/{pid}.zarr"


def upload_silver_sidecar(pid: str, sidecar: dict) -> str:
    key = f"{PROCESSED_PREFIX}/{pid}_metadata.json"
    body = json.dumps(sidecar, ensure_ascii=False, indent=2).encode("utf-8")
    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=body,
        ContentType="application/json",
    )
    logger.info("Uploaded silver sidecar to s3://%s/%s", S3_BUCKET, key)
    return key