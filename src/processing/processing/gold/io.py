import json
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import boto3
import psutil
import xarray as xr

logger = logging.getLogger(__name__)

INPUT_DIR = "/opt/ml/processing/input"
FEATURE_GROUP_NAME = "crop-polygon-features"

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
_max_workers: int | None = None
_fs_client: boto3.client | None = None


def get_workers() -> int:
    global _max_workers
    if _max_workers is None:
        from processing.gold.config import load_config

        _max_workers = load_config().get("workers", 10)
    return _max_workers


def _get_fs_client() -> boto3.client:
    global _fs_client
    if _fs_client is None:
        _fs_client = boto3.client("sagemaker-featurestore-runtime")
        logger.info("Created FeatureStore Runtime client")
    return _fs_client


def discover_silver_sidecars(input_dir: str = INPUT_DIR) -> list[str]:
    from pathlib import Path

    sidecar_files = list(Path(input_dir).rglob("*_metadata.json"))
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


def reset():
    global _ingested_count, _pending_records, _fs_client
    _ingested_count = 0
    _pending_records = []
    _fs_client = None