import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import psutil
import s3fs as s3fs_lib
from processing.bronze.config import get_copernicus_creds, load_config
from processing.bronze.download import download_polygon
from processing.bronze.io import load_polygons, load_sidecar, should_process, upload_sidecar
from processing.bronze.sidecar import build_sidecar, polygon_id

S3_BUCKET = os.environ["S3_BUCKET"]
POLYGONS_KEY = os.environ["POLYGONS_KEY"]
GIT_SHA = os.environ.get("GIT_SHA", "unknown")
METRICS_INTERVAL = int(os.environ.get("METRICS_INTERVAL", "120"))
OFFSET = int(os.environ.get("OFFSET", "0"))
LIMIT = int(os.environ.get("LIMIT", "0"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

completed = 0
skipped = 0
completed_lock = threading.Lock()
job_stats_lock = threading.Lock()
total_volume = 0


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


def process_polygon(row, config: dict, copernicus_creds: dict):
    global completed, skipped
    pid = polygon_id(row)
    logger.info("Processing polygon %s", pid)

    sidecar = load_sidecar(pid)
    if not should_process(sidecar, GIT_SHA):
        logger.info("Polygon %s already up-to-date, skipping", pid)
        with completed_lock:
            skipped += 1
        return

    s3 = s3fs_lib.S3FileSystem(anon=False)
    zarr_key, volume = download_polygon(pid, row, config, copernicus_creds, s3)
    if zarr_key is None:
        logger.warning("No data for %s, skipping sidecar", pid)
        return

    global total_volume
    with job_stats_lock:
        total_volume += volume

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
    if OFFSET > 0 or LIMIT > 0:
        start = OFFSET
        end = OFFSET + LIMIT if LIMIT > 0 else len(gdf)
        gdf = gdf.iloc[start:end]
    logger.info("Columns: %s", list(gdf.columns))
    logger.info("CRS: %s", gdf.crs)

    max_workers = config["workers"]

    logger.info(
        "Starting bronze processing: %d polygons, %d workers",
        len(gdf),
        max_workers,
    )

    global completed
    completed = 0
    global skipped
    skipped = 0
    global total_volume
    total_volume = 0
    wall_start = time.monotonic()
    stop_event = threading.Event()
    metrics_thread = threading.Thread(
        target=log_metrics, args=(stop_event, len(gdf)), daemon=True
    )
    metrics_thread.start()

    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(process_polygon, row, config, copernicus_creds): idx
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

    wall_elapsed = time.monotonic() - wall_start
    n_ok = completed
    n_skipped = skipped
    logger.info(
        "SUMMARY workers=%d jobs_ok=%d skipped=%d/%d wall_time=%.1fs",
        max_workers,
        n_ok,
        n_skipped,
        len(gdf),
        wall_elapsed,
    )
    if n_ok > 0:
        avg_time = wall_elapsed / n_ok
        avg_volume = total_volume / n_ok
        logger.info(
            "DETAIL avg_time=%.1fs/job avg_volume=%.0fpx",
            avg_time,
            avg_volume,
        )

    logger.info("Bronze processing complete for %d polygons", len(gdf))


if __name__ == "__main__":
    main()
