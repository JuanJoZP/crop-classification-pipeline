import logging
import os
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import psutil
import s3fs as s3fs_lib
from processing.bronze.config import get_copernicus_creds, load_config
from processing.bronze.download import download_polygon
from processing.bronze.io import load_polygons, upload_sidecar
from processing.bronze.sidecar import build_sidecar, polygon_id

S3_BUCKET = os.environ["S3_BUCKET"]
POLYGONS_KEY = os.environ["POLYGONS_KEY"]
GIT_SHA = os.environ.get("GIT_SHA", "unknown")
METRICS_INTERVAL = int(os.environ.get("METRICS_INTERVAL", "120"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

completed = 0
completed_lock = threading.Lock()
job_stats_lock = threading.Lock()
job_stats = defaultdict(list)


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


def process_polygon(
    row, config: dict, copernicus_creds: dict, s3: s3fs_lib.S3FileSystem
):
    global completed
    pid = polygon_id(row)
    logger.info("Processing polygon %s", pid)

    t0 = time.monotonic()
    zarr_key, volume = download_polygon(pid, row, config, copernicus_creds, s3)
    elapsed = time.monotonic() - t0
    if zarr_key is None:
        logger.warning("No data for %s, skipping sidecar", pid)
        return

    with job_stats_lock:
        job_stats["elapsed"].append(elapsed)
        job_stats["volume"].append(volume)

    processing_timestamp = datetime.now(timezone.utc).isoformat()
    sidecar = build_sidecar(row, processing_timestamp, GIT_SHA, POLYGONS_KEY)
    sidecar["processing_bronze_metadata"]["zarr_key"] = zarr_key
    upload_sidecar(pid, sidecar)
    logger.info("Polygon %s complete", pid)
    with completed_lock:
        completed += 1


def main():
    config = load_config()
    copernicus_creds = get_copernicus_creds()
    gdf = load_polygons(POLYGONS_KEY)
    logger.info("Columns: %s", list(gdf.columns))
    logger.info("CRS: %s", gdf.crs)

    cpu_count = os.cpu_count() or 1
    max_workers = config["workers_per_core"] * cpu_count
    s3 = s3fs_lib.S3FileSystem(anon=False, max_connections=max_workers)

    logger.info(
        "Starting bronze processing: %d polygons, %d workers",
        len(gdf),
        max_workers,
    )

    global completed
    completed = 0
    stop_event = threading.Event()
    metrics_thread = threading.Thread(
        target=log_metrics, args=(stop_event, len(gdf)), daemon=True
    )
    metrics_thread.start()

    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(process_polygon, row, config, copernicus_creds, s3): idx
                for idx, row in gdf.iterrows()
            }
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception:
                    logger.exception("Polygon job failed")
    finally:
        stop_event.set()
        metrics_thread.join(timeout=5)

    if job_stats["elapsed"]:
        n = len(job_stats["elapsed"])
        avg_time = sum(job_stats["elapsed"]) / n
        avg_volume = sum(job_stats["volume"]) / n
        logger.info(
            "SUMMARY workers=%d jobs=%d avg_time=%.1fs avg_volume=%.6fdeg2",
            max_workers,
            n,
            avg_time,
            avg_volume,
        )
    else:
        logger.info(
            "SUMMARY workers=%d jobs=0 avg_time=0s avg_volume=0deg2", max_workers
        )

    logger.info("Bronze processing complete for %d polygons", len(gdf))


if __name__ == "__main__":
    main()
