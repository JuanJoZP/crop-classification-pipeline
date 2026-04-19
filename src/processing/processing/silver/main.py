import logging
import os
import time
from datetime import datetime, timezone

import s3fs as s3fs_lib

from processing.silver.config import load_config
from processing.silver.io import (
    discover_parcels,
    load_bronze_sidecar,
    load_silver_sidecar,
    load_zarr,
    save_zarr,
    upload_silver_sidecar,
)
from processing.silver.parcel import parse_parcel_info
from processing.silver.preprocessor import EmptyDatasetError, SilverPreprocessor
from processing.silver.sidecar import build_sidecar, should_process

S3_BUCKET = os.environ["S3_BUCKET"]
GIT_SHA = os.environ.get("GIT_SHA", "unknown")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

completed = 0
skipped = 0
failed = 0


def process_parcel(bronze_sidecar_key: str, cfg: dict, s3: s3fs_lib.S3FileSystem):
    global completed, skipped, failed

    bronze_sidecar = load_bronze_sidecar(bronze_sidecar_key)
    parcel = parse_parcel_info(bronze_sidecar)
    pid = parcel.pid
    logger.info("Processing parcel %s", pid)

    silver_sidecar = load_silver_sidecar(pid)
    if not should_process(bronze_sidecar, silver_sidecar, GIT_SHA):
        logger.info("Parcel %s already processed with same SHA, skipping", pid)
        skipped += 1
        return

    try:
        dataset = load_zarr(pid, s3)
    except Exception:
        logger.exception("Failed to load zarr for parcel %s", pid)
        failed += 1
        return

    logger.info("Loading dataset into memory for parcel=%s", pid)
    dataset = dataset.load()

    preprocessor = SilverPreprocessor(dataset, parcel, cfg)
    try:
        preprocessor.preprocess()
    except EmptyDatasetError:
        logger.warning("Parcel %s has no data after preprocessing, skipping", pid)
        skipped += 1
        return

    save_zarr(pid, preprocessor.dataset, s3)

    processing_timestamp = datetime.now(timezone.utc).isoformat()
    silver_sidecar_data = build_sidecar(bronze_sidecar, processing_timestamp, GIT_SHA)
    upload_silver_sidecar(pid, silver_sidecar_data)

    completed += 1
    logger.info("Parcel %s complete", pid)


def main():
    cfg = load_config()
    s3 = s3fs_lib.S3FileSystem(anon=False)

    sidecar_keys = discover_parcels()
    logger.info("Found %d parcels to process", len(sidecar_keys))

    wall_start = time.monotonic()

    for bronze_sidecar_key in sidecar_keys:
        try:
            process_parcel(bronze_sidecar_key, cfg, s3)
        except Exception:
            logger.exception("Failed to process parcel from %s", bronze_sidecar_key)
            failed += 1

    wall_elapsed = time.monotonic() - wall_start
    logger.info(
        "SUMMARY completed=%d skipped=%d failed=%d total=%d wall_time=%.1fs",
        completed,
        skipped,
        failed,
        len(sidecar_keys),
        wall_elapsed,
    )


if __name__ == "__main__":
    main()