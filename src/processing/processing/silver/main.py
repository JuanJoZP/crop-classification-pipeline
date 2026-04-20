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
OFFSET = int(os.environ.get("OFFSET", "0"))
LIMIT = int(os.environ.get("LIMIT", "0"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def process_parcel(
    bronze_sidecar_key: str, cfg: dict, s3: s3fs_lib.S3FileSystem, counters: dict
):
    pid = None
    try:
        bronze_sidecar = load_bronze_sidecar(bronze_sidecar_key)
        parcel = parse_parcel_info(bronze_sidecar)
        pid = parcel.pid
        logger.info("Processing parcel %s", pid)

        silver_sidecar = load_silver_sidecar(pid)
        if not should_process(bronze_sidecar, silver_sidecar, GIT_SHA):
            logger.info("Parcel %s already processed with same SHA, skipping", pid)
            counters["skipped"] += 1
            return

        dataset = load_zarr(pid, s3)
        logger.info("Loading dataset into memory for parcel=%s", pid)
        dataset = dataset.load()

        preprocessor = SilverPreprocessor(dataset, parcel, cfg)
        preprocessor.preprocess()
        save_zarr(pid, preprocessor.dataset, s3)

        processing_timestamp = datetime.now(timezone.utc).isoformat()
        silver_sidecar_data = build_sidecar(
            bronze_sidecar, processing_timestamp, GIT_SHA
        )
        upload_silver_sidecar(pid, silver_sidecar_data)

        counters["completed"] += 1
        logger.info("Parcel %s complete", pid)

    except EmptyDatasetError:
        if pid:
            logger.warning("Parcel %s has no data after preprocessing, skipping", pid)
        counters["skipped"] += 1
    except Exception:
        if pid:
            logger.exception("Failed to process parcel %s", pid)
        counters["failed"] += 1


def main():
    counters = {"completed": 0, "skipped": 0, "failed": 0}
    cfg = load_config()
    s3 = s3fs_lib.S3FileSystem(anon=False)

    sidecar_keys = discover_parcels()
    logger.info("Found %d parcels to process (offset=%d, limit=%d)", len(sidecar_keys), OFFSET, LIMIT)

    wall_start = time.monotonic()

    for bronze_sidecar_key in sidecar_keys:
        process_parcel(bronze_sidecar_key, cfg, s3, counters)

    wall_elapsed = time.monotonic() - wall_start
    logger.info(
        "SUMMARY completed=%d skipped=%d failed=%d total=%d wall_time=%.1fs",
        counters["completed"],
        counters["skipped"],
        counters["failed"],
        len(sidecar_keys),
        wall_elapsed,
    )


if __name__ == "__main__":
    main()
