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

INPUT_DIR = os.environ.get("GOLD_INPUT_DIR", "/opt/ml/processing/processed")
FEATURE_GROUP_NAME = os.environ.get("FEATURE_GROUP_NAME", "crop-polygon-features")

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


def load_silver_sidecar(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def load_silver_zarr(pid: str, input_dir: str = INPUT_DIR) -> xr.Dataset:
    zarr_path = os.path.join(input_dir, f"{pid}.zarr")
    return xr.open_zarr(zarr_path, consolidated=True)


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


def check_lineage_athena(objectids: list[str], current_gold_sha: str) -> dict[str, bool]:
    if not objectids:
        return {}

    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION", "us-west-2")
    athena = boto3.client("athena", region_name=region)

    database = "sagemaker_featurestore"
    table = f'"{FEATURE_GROUP_NAME}"'

    ids_str = ", ".join(f"'{oid}'" for oid in objectids)
    query = f"SELECT objectid, metadata FROM {table} WHERE objectid IN ({ids_str})"

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
            reason = result["QueryExecution"]["Status"].get("StateChangeReason", "unknown")
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