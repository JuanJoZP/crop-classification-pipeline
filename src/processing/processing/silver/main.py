import logging
import os
import threading
import time
from datetime import datetime, timezone

import psutil
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
METRICS_INTERVAL = int(os.environ.get("METRICS_INTERVAL", "120"))
OFFSET = int(os.environ.get("OFFSET", "0"))
LIMIT = int(os.environ.get("LIMIT", "0"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

completed = 0
skipped = 0
failed = 0
completed_lock = threading.Lock()


def log_metrics(stop_event: threading.Event, total: int):
    process = psutil.Process()
    while not stop_event.is_set():
        cpu = process.cpu_percent(interval=None)
        mem = process.memory_info()
        net_io = psutil.net_io_counters()
        with completed_lock:
            done = completed
        logger.info(
            "METRICS cpu=%.1f%% mem_rss=%.0fMB net_bytes_sent=%.0fMB net_bytes_recv=%.0fMB progress=%d/%d",
            cpu,
            mem.rss / 1024 / 1024,
            net_io.bytes_sent / 1024 / 1024,
            net_io.bytes_recv / 1024 / 1024,
            done,
            total,
        )
        stop_event.wait(METRICS_INTERVAL)


def process_parcel(
    bronze_sidecar_key: str, cfg: dict, s3: s3fs_lib.S3FileSystem
):
    global completed, skipped, failed
    pid = None
    try:
        bronze_sidecar = load_bronze_sidecar(bronze_sidecar_key)
        parcel = parse_parcel_info(bronze_sidecar)
        pid = parcel.pid
        logger.info("Processing parcel %s", pid)

        silver_sidecar = load_silver_sidecar(pid)
        if not should_process(bronze_sidecar, silver_sidecar, GIT_SHA):
            logger.info("Parcel %s already processed with same SHA, skipping", pid)
            with completed_lock:
                skipped += 1
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

        with completed_lock:
            completed += 1
        logger.info("Parcel %s complete", pid)

    except EmptyDatasetError:
        if pid:
            logger.warning("Parcel %s has no data after preprocessing, skipping", pid)
        with completed_lock:
            skipped += 1
    except Exception:
        if pid:
            logger.exception("Failed to process parcel %s", pid)
        with completed_lock:
            failed += 1


def main():
    global completed, skipped, failed
    completed = 0
    skipped = 0
    failed = 0

    cfg = load_config()
    s3 = s3fs_lib.S3FileSystem(anon=False)

    sidecar_keys = discover_parcels()
    logger.info("Found %d parcels to process (offset=%d, limit=%d)", len(sidecar_keys), OFFSET, LIMIT)

    wall_start = time.monotonic()
    stop_event = threading.Event()
    metrics_thread = threading.Thread(
        target=log_metrics, args=(stop_event, len(sidecar_keys)), daemon=True
    )
    metrics_thread.start()

    try:
        for bronze_sidecar_key in sidecar_keys:
            process_parcel(bronze_sidecar_key, cfg, s3)
    finally:
        stop_event.set()
        metrics_thread.join(timeout=5)

    wall_elapsed = time.monotonic() - wall_start
    n_ok = completed
    n_skipped = skipped
    n_failed = failed
    n_total = len(sidecar_keys)
    logger.info(
        "SUMMARY completed=%d skipped=%d failed=%d total=%d wall_time=%.1fs",
        n_ok,
        n_skipped,
        n_failed,
        n_total,
        wall_elapsed,
    )
    if n_ok > 0:
        avg_time = wall_elapsed / n_ok
        logger.info(
            "DETAIL avg_time=%.1fs/parcel",
            avg_time,
        )


if __name__ == "__main__":
    main()
