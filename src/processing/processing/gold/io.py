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
import xarray as xr

logger = logging.getLogger(__name__)

INPUT_DIR = "/tmp/gold/processed"

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

FEATURE_GROUP_NAME = os.environ.get("FEATURE_GROUP_NAME", "crop-polygon-features")
S3_BUCKET = os.environ["S3_BUCKET"]
PROCESSED_PREFIX = os.environ.get("PROCESSED_PREFIX", "processed")
POLYGONS_KEY = os.environ.get("POLYGONS_KEY", "")
RAM_THRESHOLD_PERCENT = int(os.environ.get("RAM_THRESHOLD_PERCENT", "80"))

_pending_records: list[dict] = []
_pending_lock = threading.Lock()
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
        kwargs = {}
        region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
        if region:
            kwargs["region_name"] = region
        _fs_client = boto3.client("sagemaker-featurestore-runtime", **kwargs)
    return _fs_client


def discover_silver_sidecars() -> list[str]:
    from pathlib import Path

    sidecar_files = sorted(Path(INPUT_DIR).rglob("*_metadata.json"))
    logger.info("Found %d silver sidecars", len(sidecar_files))
    return [str(f) for f in sidecar_files]


def _polygon_id_from_feature(feature: dict) -> str:
    props = feature.get("properties", {})
    service = props.get("service", "")
    objectid = str(props.get("objectid", "")).replace(" ", "_")
    return f"{service}_{objectid}"


def discover_silver_s3(polygon_ids: list[str]) -> list[tuple[str, str]]:
    s3_client = boto3.client("s3")
    results: list[tuple[str, str]] = []

    for pid in polygon_ids:
        prefix = f"{PROCESSED_PREFIX}/{pid}"
        paginator = s3_client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.endswith("_metadata.json"):
                    local_path = os.path.join(INPUT_DIR, os.path.basename(key))
                    results.append((key, local_path))

    logger.info("Found %d silver sidecars in S3", len(results))
    return results


def download_silver_files(s3_file_list: list[tuple[str, str]]) -> list[str]:
    os.makedirs(INPUT_DIR, exist_ok=True)
    s3_client = boto3.client("s3")

    def download_file(key: str, local_path: str) -> Optional[str]:
        if os.path.exists(local_path):
            return local_path
        try:
            s3_client.download_file(S3_BUCKET, key, local_path)
            return local_path
        except Exception as e:
            logger.error("Failed to download s3://%s/%s: %s", S3_BUCKET, key, e)
            return None

    all_download_args: list[tuple[str, str]] = []
    for key, local_path in s3_file_list:
        all_download_args.append((key, local_path))
        if key.endswith("_metadata.json"):
            all_download_args.append(
                (
                    key.replace("_metadata.json", ".nc"),
                    local_path.replace("_metadata.json", ".nc"),
                )
            )

    downloaded = []
    with ThreadPoolExecutor(max_workers=get_workers()) as executor:
        futures = {
            executor.submit(download_file, k, p): p for k, p in all_download_args
        }
        for future in as_completed(futures):
            result = future.result()
            if result and result.endswith("_metadata.json"):
                downloaded.append(result)

    logger.info("Downloaded %d sidecars (+ .nc files)", len(downloaded))
    return downloaded


def discover_silver_from_polygons_key() -> list[str]:
    if not POLYGONS_KEY:
        logger.warning("POLYGONS_KEY not set, falling back to scanning local dir")
        return discover_silver_sidecars()

    s3_client = boto3.client("s3")
    response = s3_client.get_object(Bucket=S3_BUCKET, Key=POLYGONS_KEY)
    geojson = json.loads(response["Body"].read().decode("utf-8"))

    polygon_ids = [_polygon_id_from_feature(f) for f in geojson.get("features", [])]
    polygon_ids = [p for p in polygon_ids if p]
    logger.info("Extracted %d polygon_ids from polygons JSON", len(polygon_ids))

    s3_file_list = discover_silver_s3(polygon_ids)
    if s3_file_list:
        download_silver_files(s3_file_list)

    return discover_silver_sidecars()


def load_silver_sidecar(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def load_silver_dataset(pid: str) -> xr.Dataset:
    nc_path = os.path.join(INPUT_DIR, f"{pid}.nc")
    zarr_path = os.path.join(INPUT_DIR, f"{pid}.zarr")

    if os.path.exists(nc_path):
        return xr.open_dataset(nc_path, engine="netcdf4")
    if os.path.isdir(zarr_path):
        return xr.open_zarr(zarr_path, consolidated=True)
    raise FileNotFoundError(f"No dataset found for parcel {pid}")


def get_series_as_string(dataset: xr.Dataset, var_name: str) -> str:
    if var_name not in dataset.data_vars:
        return ""
    arr = dataset[var_name].values
    mean_series = arr.mean(axis=0) if arr.ndim == 2 else arr
    return ",".join([str(float(x)) for x in mean_series])


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
            FeatureGroupName=FEATURE_GROUP_NAME, Record=feature_values
        )
        return True
    except Exception as e:
        logger.error("put_record failed for objectid=%s: %s", record.get("objectid"), e)
        return False


def add_to_batch(record: dict):
    global _pending_records
    with _pending_lock:
        _pending_records.append(record)
        mem_percent = psutil.virtual_memory().percent
        if mem_percent >= RAM_THRESHOLD_PERCENT:
            logger.info(
                "RAM %.1f%% >= threshold, flushing %d records",
                mem_percent,
                len(_pending_records),
            )
            records = _pending_records
            _pending_records = []
        else:
            return
    _ingest_batch(records)


def _ingest_batch(records: list[dict]):
    if not records:
        return
    with ThreadPoolExecutor(max_workers=get_workers()) as executor:
        futures = {executor.submit(_put_record, r): r for r in records}
        success = sum(1 for f in as_completed(futures) if f.result())
    global _ingested_count
    with _ingested_lock:
        _ingested_count += success
    logger.info("Ingested %d/%d records via Feature Store", success, len(records))


def flush_batch():
    global _pending_records
    with _pending_lock:
        if not _pending_records:
            return
        records = _pending_records
        _pending_records = []
    _ingest_batch(records)


def get_ingested_count() -> int:
    with _ingested_lock:
        return _ingested_count


def get_queue_size() -> int:
    with _pending_lock:
        return len(_pending_records)


def _resolve_athena_table() -> tuple[str, str]:
    region = os.environ.get("AWS_REGION") or os.environ.get(
        "AWS_DEFAULT_REGION", "us-west-2"
    )
    glue = boto3.client("glue", region_name=region)
    database = "sagemaker_featurestore"
    fg_name = FEATURE_GROUP_NAME.replace("-", "_")
    tables = glue.get_tables(DatabaseName=database, Expression=f"{fg_name}*").get(
        "TableList", []
    )
    if not tables:
        raise RuntimeError(f"No Glue table found for '{fg_name}*'")
    return database, tables[0]["Name"]


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
        if state == "SUCCEEDED":
            break
        if state in ("FAILED", "CANCELLED"):
            logger.warning(
                "Athena query failed: %s",
                result["QueryExecution"]["Status"].get("StateChangeReason"),
            )
            return {}
        time.sleep(1)

    rows = athena.get_query_results(QueryExecutionId=execution_id)
    existing = {oid: False for oid in objectids}
    for row in rows.get("ResultSet", {}).get("Rows", [])[1:]:
        cols = row["Data"]
        oid = cols[0]["VarCharValue"]
        metadata_str = cols[1].get("VarCharValue", "")
        try:
            stored_sha = json.loads(metadata_str).get("gold_git_sha", "")
        except (json.JSONDecodeError, TypeError):
            stored_sha = ""
        existing[oid] = stored_sha == current_gold_sha
    return existing


def reset():
    global _ingested_count, _pending_records, _fs_client
    with _pending_lock:
        _pending_records = []
    _ingested_count = 0
    _fs_client = None
