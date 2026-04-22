from __future__ import annotations

import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import boto3
import psutil
import s3fs
import xarray as xr

logger = logging.getLogger(__name__)

INPUT_DIR = os.environ.get("GOLD_INPUT_DIR", "/opt/ml/processing/processed")
FEATURE_GROUP_NAME = os.environ.get("FEATURE_GROUP_NAME", "crop-polygon-features")
S3_BUCKET = os.environ["S3_BUCKET"]
PROCESSED_PREFIX = os.environ.get("PROCESSED_PREFIX", "processed")
POLYGONS_KEY = os.environ.get("POLYGONS_KEY", "")

LIST_BANDS = [
    "coastal",
    "blue",
    "green",
    "red",
    "rededge1",
    "rededge2",
    "rededge3",
    "nir",
    "nir08",
    "nir09",
    "swir16",
    "swir22",
    "aot",
]

LIST_INDEXES = [
    "veg_index",
    "ndvi",
    "evi",
    "gndvi",
    "savi",
    "msavi",
    "ndwi",
    "gcvi",
    "vari",
    "ndre",
    "cire",
    "ndmi",
    "mndwi",
    "psri",
    "rendvi",
]

RAM_THRESHOLD_PERCENT = int(os.environ.get("RAM_THRESHOLD_PERCENT", "80"))

_pending_records: list[dict] = []
_ingested_count: int = 0
_ingested_lock = threading.Lock()
_max_workers: Optional[int] = None
_fs_client: Optional[boto3.client] = None


def get_workers() -> int:
    global _max_workers
    if _max_workers is None:
        from processing.gold.config import load_config

        _max_workers = load_config().get("workers", 10)
    return _max_workers


def _get_fs_client() -> boto3.client:
    global _fs_client
    if _fs_client is None:
        import boto3 as _boto3

        kwargs = {}
        region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
        if region:
            kwargs["region_name"] = region
        _fs_client = _boto3.client("sagemaker-featurestore-runtime", **kwargs)
        logger.info("Created FeatureStore Runtime client")
    return _fs_client


def discover_silver_sidecars(input_dir: str = INPUT_DIR) -> list[str]:
    from pathlib import Path

    sidecar_files = sorted(Path(input_dir).rglob("*_metadata.json"))
    logger.info("Found %d silver sidecars", len(sidecar_files))
    return [str(f) for f in sidecar_files]


def _polygon_id_from_feature(feature: dict) -> str:
    props = feature.get("properties", {})
    service = props.get("service", "")
    objectid = props.get("objectid", "")
    if isinstance(objectid, str):
        objectid = objectid.replace(" ", "_")
    return f"{service}_{objectid}"


def discover_silver_from_polygons_key() -> list[str]:
    if not POLYGONS_KEY:
        logger.warning("POLYGONS_KEY not set, falling back to scanning input_dir")
        return discover_silver_sidecars(INPUT_DIR)

    logger.info("Loading polygons from s3://%s/%s", S3_BUCKET, POLYGONS_KEY)

    s3_client = boto3.client("s3")
    response = s3_client.get_object(Bucket=S3_BUCKET, Key=POLYGONS_KEY)
    body = response["Body"].read().decode("utf-8")
    geojson = json.loads(body)

    polygon_ids = []
    for feature in geojson.get("features", []):
        pid = _polygon_id_from_feature(feature)
        if pid:
            polygon_ids.append(pid)

    logger.info("Extracted %d polygon_ids from polygons JSON", len(polygon_ids))

    s3 = s3fs.S3FileSystem(anon=False)
    paginator = s3_client.get_paginator("list_objects_v2")
    processed_prefix = f"{PROCESSED_PREFIX}/"

    sidecar_paths = set()
    for pid in polygon_ids:
        base_nc = f"{processed_prefix}{pid}.nc"
        base_zarr = f"{processed_prefix}{pid}.zarr"
        base_nc_url = f"s3://{S3_BUCKET}/{base_nc}"
        base_zarr_url = f"s3://{S3_BUCKET}/{base_zarr}"

        if s3.exists(base_nc_url):
            sidecar_paths.add(base_nc)
        elif s3.exists(base_zarr_url):
            sidecar_paths.add(base_zarr)
        else:
            split_prefix = f"{processed_prefix}{pid}_"
            pages = paginator.paginate(Bucket=S3_BUCKET, Prefix=split_prefix)
            for page in pages:
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    if key.endswith(".nc") or key.endswith(".zarr"):
                        sidecar_paths.add(key)

    logger.info("Found %d silver datasets (including splits)", len(sidecar_paths))
    return sorted(sidecar_paths)

    logger.info("Found %d silver datasets with data", len(sidecar_paths))
    return sidecar_paths


def load_silver_sidecar(path: str) -> dict:
    if path.startswith("s3://"):
        s3_client = boto3.client("s3")
        bucket, key = path.replace("s3://", "").split("/", 1)
        response = s3_client.get_object(Bucket=bucket, Key=key)
        body = response["Body"].read().decode("utf-8")
        return json.loads(body)
    with open(path) as f:
        return json.load(f)


def load_silver_dataset(pid: str, input_dir: str = INPUT_DIR) -> xr.Dataset:
    nc_path = os.path.join(input_dir, f"{pid}.nc")
    zarr_path = os.path.join(input_dir, f"{pid}.zarr")

    if os.path.exists(nc_path):
        return xr.open_dataset(nc_path, engine="netcdf4")

    if os.path.isdir(zarr_path):
        return xr.open_zarr(zarr_path, consolidated=True)

    raise FileNotFoundError(
        f"No dataset found for parcel {pid} at {nc_path} or {zarr_path}"
    )


def load_silver_dataset_s3(pid: str) -> xr.Dataset:
    s3 = s3fs.S3FileSystem(anon=False)
    nc_url = f"s3://{S3_BUCKET}/{PROCESSED_PREFIX}/{pid}.nc"
    zarr_url = f"s3://{S3_BUCKET}/{PROCESSED_PREFIX}/{pid}.zarr"

    if s3.exists(nc_url):
        logger.info("Loading NetCDF from %s", nc_url)
        store = s3fs.S3Map(root=nc_url.replace("s3://", "").split("/", 1)[1], s3=s3, check=False)
        return xr.open_dataset(store, engine="netcdf4")

    if s3.exists(zarr_url):
        logger.info("Loading zarr from %s", zarr_url)
        store = s3fs.S3Map(root=zarr_url.replace("s3://", "").split("/", 1)[1], s3=s3, check=False)
        return xr.open_zarr(store, consolidated=True)

    raise FileNotFoundError(
        f"No dataset found for parcel {pid} at {nc_url} or {zarr_url}"
    )


def load_silver_sidecar_s3(pid: str) -> dict:
    s3_client = boto3.client("s3")
    key = f"{PROCESSED_PREFIX}/{pid}_metadata.json"
    response = s3_client.get_object(Bucket=S3_BUCKET, Key=key)
    body = response["Body"].read().decode("utf-8")
    return json.loads(body)


load_silver_zarr = load_silver_dataset


def get_series_as_string(dataset: xr.Dataset, var_name: str) -> str:
    if var_name not in dataset.data_vars:
        return ""

    arr = dataset[var_name].values
    if arr.ndim == 2:
        mean_series = arr.mean(axis=0)
    else:
        mean_series = arr

    return ",".join([str(float(x)) for x in mean_series])


def get_ingested_count() -> int:
    with _ingested_lock:
        return _ingested_count


def _add_ingested(n: int):
    global _ingested_count
    with _ingested_lock:
        _ingested_count += n


def _put_record(record: dict) -> bool:
    feature_values = [
        {
            "FeatureName": k,
            "ValueAsString": str(v) if not isinstance(v, list) else json.dumps(v),
        }
        for k, v in record.items()
    ]
    try:
        _get_fs_client().put_record(
            FeatureGroupName=FEATURE_GROUP_NAME,
            Record=feature_values,
        )
        return True
    except Exception as e:
        logger.error("put_record failed for objectid=%s: %s", record.get("objectid"), e)
        return False


def _ingest_records(records: list[dict]):
    if not records:
        return

    max_workers = get_workers()
    success = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_put_record, r): r for r in records}
        for future in as_completed(futures):
            if future.result():
                success += 1

    _add_ingested(success)
    logger.info("Ingested %d/%d records via Feature Store", success, len(records))


def flush_batch():
    global _pending_records
    if _pending_records:
        records = _pending_records
        _pending_records = []
        _ingest_records(records)


def add_to_batch(record: dict):
    _pending_records.append(record)
    mem_percent = psutil.virtual_memory().percent
    if mem_percent >= RAM_THRESHOLD_PERCENT:
        logger.info(
            "RAM usage %.1f%% >= threshold %d%%, flushing %d pending records",
            mem_percent,
            RAM_THRESHOLD_PERCENT,
            len(_pending_records),
        )
        flush_batch()


def get_queue_size() -> int:
    return len(_pending_records)


def _resolve_athena_table() -> str:
    region = os.environ.get("AWS_REGION") or os.environ.get(
        "AWS_DEFAULT_REGION", "us-west-2"
    )
    glue = boto3.client("glue", region_name=region)
    database = "sagemaker_featurestore"

    fg_name = FEATURE_GROUP_NAME.replace("-", "_")
    response = glue.get_tables(DatabaseName=database, Expression=f"{fg_name}*")
    tables = response.get("TableList", [])
    if not tables:
        raise RuntimeError(
            f"No Glue table found matching '{fg_name}*' in database '{database}'. "
            f"Available: {[t['Name'] for t in glue.get_tables(DatabaseName=database).get('TableList', [])]}"
        )

    table_name = tables[0]["Name"]
    logger.info("Resolved Athena table: %s.%s", database, table_name)
    return database, table_name


def check_lineage_athena(
    objectids: list[str], current_gold_sha: str
) -> dict[str, bool]:
    if not objectids:
        return {}

    region = os.environ.get("AWS_REGION") or os.environ.get(
        "AWS_DEFAULT_REGION", "us-west-2"
    )
    athena = boto3.client("athena", region_name=region)

    database, table_name = _resolve_athena_table()

    ids_str = ", ".join(f"'{oid}'" for oid in objectids)
    query = (
        f'SELECT objectid, metadata FROM "{table_name}" WHERE objectid IN ({ids_str})'
    )

    execution = athena.start_query_execution(
        QueryString=query,
        QueryExecutionContext={"Database": database},
        WorkGroup="primary",
    )
    execution_id = execution["QueryExecutionId"]

    while True:
        result = athena.get_query_execution(QueryExecutionId=execution_id)
        state = result["QueryExecution"]["Status"]["State"]
        if state in ("SUCCEEDED",):
            break
        if state in ("FAILED", "CANCELLED"):
            reason = result["QueryExecution"]["Status"].get(
                "StateChangeReason", "unknown"
            )
            logger.warning("Athena query failed: %s", reason)
            return {}
        time.sleep(1)

    rows = athena.get_query_results(QueryExecutionId=execution_id)
    existing = {}
    for row in rows.get("ResultSet", {}).get("Rows", [])[1:]:
        cols = row["Data"]
        oid = cols[0]["VarCharValue"]
        metadata_str = cols[1].get("VarCharValue", "")
        try:
            metadata = json.loads(metadata_str)
            stored_sha = metadata.get("gold_git_sha", "")
        except (json.JSONDecodeError, TypeError):
            stored_sha = ""
        existing[oid] = stored_sha == current_gold_sha

    return existing


def reset():
    global _ingested_count, _pending_records, _fs_client
    _ingested_count = 0
    _pending_records = []
    _fs_client = None
