import json
import logging
import os
import threading
from typing import Any

import pandas as pd
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
_feature_definitions: dict | None = None


def get_workers() -> int:
    global _max_workers
    if _max_workers is None:
        from processing.gold.config import load_config

        _max_workers = load_config().get("workers", 10)
    return _max_workers


def _get_feature_definitions() -> dict:
    global _feature_definitions
    if _feature_definitions is None:
        import boto3

        client = boto3.client("sagemaker")
        response = client.describe_feature_group(FeatureGroupName=FEATURE_GROUP_NAME)
        _feature_definitions = {
            fd["FeatureName"]: {"Type": fd["FeatureType"]}
            for fd in response["FeatureDefinitions"]
        }
        logger.info(
            "Loaded %d feature definitions from Feature Group '%s'",
            len(_feature_definitions),
            FEATURE_GROUP_NAME,
        )
    return _feature_definitions


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


def _ingest_records(records: list[dict]):
    if not records:
        return

    from sagemaker.mlops.feature_store import IngestionError, IngestionManagerPandas

    max_workers = get_workers()
    df = pd.DataFrame(records)
    feature_defs = _get_feature_definitions()

    try:
        manager = IngestionManagerPandas(
            feature_group_name=FEATURE_GROUP_NAME,
            feature_definitions=feature_defs,
            max_workers=max_workers,
        )
        manager.run(data_frame=df, wait=True)
        _add_ingested(len(records))
        logger.info("Ingested %d records via Feature Store SDK", len(records))
    except IngestionError as e:
        logger.error("Ingestion failed for %d rows: %s", len(e.failed_rows), e.message)
    except Exception as e:
        logger.error("Ingestion error: %s", e)


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
    global _ingested_count, _pending_records
    _ingested_count = 0
    _pending_records = []
