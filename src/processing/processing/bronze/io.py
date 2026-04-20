import json
import logging
import os

import boto3
import geopandas as gpd

S3_BUCKET = os.environ["S3_BUCKET"]
RAW_PREFIX = os.environ.get("RAW_PREFIX", "raw")

s3_client = boto3.client("s3")

logger = logging.getLogger(__name__)


def load_polygons(key: str) -> gpd.GeoDataFrame:
    logger.info("Loading polygons from s3://%s/%s", S3_BUCKET, key)
    response = s3_client.get_object(Bucket=S3_BUCKET, Key=key)
    body = response["Body"].read().decode("utf-8")
    geojson = json.loads(body)
    gdf = gpd.GeoDataFrame.from_features(geojson, crs="EPSG:4326")
    logger.info("Loaded %d polygons", len(gdf))
    return gdf


def load_sidecar(pid: str) -> dict | None:
    key = f"{RAW_PREFIX}/{pid}_metadata.json"
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=key)
        body = response["Body"].read().decode("utf-8")
        return json.loads(body)
    except s3_client.exceptions.NoSuchKey:
        return None
    except s3_client.exceptions.ClientError:
        return None


def should_process(sidecar: dict | None, git_sha: str) -> bool:
    if sidecar is None:
        return True
    existing_sha = sidecar.get("processing_bronze_metadata", {}).get("git_sha")
    if existing_sha != git_sha:
        logger.info("Sidecar git_sha=%s differs from current=%s, reprocessing", existing_sha, git_sha)
        return True
    logger.info("Sidecar git_sha matches current=%s, skipping", git_sha)
    return False


def upload_sidecar(pid: str, sidecar: dict) -> str:
    key = f"{RAW_PREFIX}/{pid}_metadata.json"
    body = json.dumps(sidecar, ensure_ascii=False, indent=2).encode("utf-8")
    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=body,
        ContentType="application/json",
    )
    logger.info("Uploaded sidecar to s3://%s/%s", S3_BUCKET, key)
    return key
