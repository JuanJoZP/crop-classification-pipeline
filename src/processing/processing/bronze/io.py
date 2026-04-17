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
