import json
import logging
import os
import tempfile

import boto3
import s3fs
import xarray as xr

S3_BUCKET = os.environ["S3_BUCKET"]
RAW_PREFIX = os.environ.get("RAW_PREFIX", "raw")
PROCESSED_PREFIX = os.environ.get("PROCESSED_PREFIX", "processed")
OFFSET = int(os.environ.get("OFFSET", "0"))
LIMIT = int(os.environ.get("LIMIT", "0"))

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

    sidecar_keys.sort()
    logger.info("Found %d bronze sidecars", len(sidecar_keys))

    if OFFSET > 0 or LIMIT > 0:
        start = OFFSET
        end = OFFSET + LIMIT if LIMIT > 0 else len(sidecar_keys)
        sidecar_keys = sidecar_keys[start:end]
        logger.info(
            "Sliced to offset=%d limit=%d -> %d sidecars",
            OFFSET,
            LIMIT,
            len(sidecar_keys),
        )

    return sidecar_keys


def _polygon_id_from_feature(feature: dict) -> str:
    props = feature.get("properties", {})
    service = props.get("service", "")
    objectid = props.get("objectid", "")
    if isinstance(objectid, str):
        objectid = objectid.replace(" ", "_")
    return f"{service}_{objectid}"


def discover_parcels_from_polygons_key(polygons_key: str, offset: int, limit: int) -> list[str]:
    logger.info("Loading polygons from s3://%s/%s", S3_BUCKET, polygons_key)

    response = s3_client.get_object(Bucket=S3_BUCKET, Key=polygons_key)
    body = response["Body"].read().decode("utf-8")
    geojson = json.loads(body)

    polygon_ids = []
    for feature in geojson.get("features", []):
        pid = _polygon_id_from_feature(feature)
        if pid:
            polygon_ids.append(pid)

    logger.info("Extracted %d polygon_ids from polygons JSON", len(polygon_ids))

    if offset > 0 or limit > 0:
        start = offset
        end = offset + limit if limit > 0 else len(polygon_ids)
        polygon_ids = polygon_ids[start:end]
        logger.info(
            "Sliced to offset=%d limit=%d -> %d polygon_ids",
            offset,
            limit,
            len(polygon_ids),
        )

    sidecar_keys = []
    for pid in polygon_ids:
        sidecar_key = f"{RAW_PREFIX}/{pid}_metadata.json"
        try:
            s3_client.head_object(Bucket=S3_BUCKET, Key=sidecar_key)
            sidecar_keys.append(sidecar_key)
        except s3_client.exceptions.NoSuchKey:
            logger.debug("No sidecar for %s, skipping", pid)
        except s3_client.exceptions.ClientError:
            logger.debug("Error checking sidecar for %s, skipping", pid)

    logger.info("Found %d sidecars with data", len(sidecar_keys))
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
    except s3_client.exceptions.ClientError:
        return None


def load_dataset(pid: str, s3: s3fs.S3FileSystem) -> xr.Dataset:
    nc_url = f"s3://{S3_BUCKET}/{RAW_PREFIX}/{pid}.nc"
    zarr_url = f"s3://{S3_BUCKET}/{RAW_PREFIX}/{pid}.zarr"

    if s3.exists(nc_url):
        logger.info("Loading NetCDF from %s", nc_url)
        fd, tmp_path = tempfile.mkstemp(suffix=".nc")
        os.close(fd)
        try:
            s3.get(nc_url, tmp_path)
            ds = xr.open_dataset(tmp_path, engine="netcdf4")
            ds = ds.load()
            ds.close()
        finally:
            os.unlink(tmp_path)
        return ds

    if s3.exists(zarr_url):
        logger.info("Loading zarr (legacy) from %s", zarr_url)
        store = s3fs.S3Map(root=zarr_url, s3=s3, check=False)
        return xr.open_zarr(store, consolidated=True)

    raise FileNotFoundError(
        f"No dataset found for parcel {pid} at {nc_url} or {zarr_url}"
    )


load_zarr = load_dataset


def save_dataset(pid: str, dataset: xr.Dataset, s3: s3fs.S3FileSystem) -> str:
    nc_key = f"{PROCESSED_PREFIX}/{pid}.nc"
    s3_url = f"s3://{S3_BUCKET}/{nc_key}"

    logger.info("Saving NetCDF to %s", s3_url)
    fd, tmp_path = tempfile.mkstemp(suffix=".nc")
    os.close(fd)
    try:
        dataset.to_netcdf(tmp_path, format="NETCDF4")
        s3.put(tmp_path, s3_url)
    finally:
        os.unlink(tmp_path)
    return nc_key


save_zarr = save_dataset


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
