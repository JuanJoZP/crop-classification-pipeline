import logging
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
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


def process_polygon(row, config: dict, copernicus_creds: dict) -> dict:
    pid = polygon_id(row)
    result = {"pid": pid, "status": "error", "completed": False, "skipped": False}
    logger.info("Processing polygon %s", pid)

    sidecar = load_sidecar(pid)
    if not should_process(sidecar, GIT_SHA):
        logger.info("Polygon %s already up-to-date, skipping", pid)
        result["skipped"] = True
        result["status"] = "skipped"
        return result

    s3 = s3fs_lib.S3FileSystem(anon=False)
    data_key, volume = download_polygon(pid, row, config, copernicus_creds, s3)
    if data_key is None:
        logger.warning("No data for %s, skipping sidecar", pid)
        result["status"] = "no_data"
        return result

    processing_timestamp = datetime.now(timezone.utc).isoformat()
    sidecar = build_sidecar(row, processing_timestamp, GIT_SHA, POLYGONS_KEY)
    sidecar["processing_bronze_metadata"]["data_key"] = data_key
    upload_sidecar(pid, sidecar)
    logger.info("Polygon %s complete", pid)
    result["completed"] = True
    result["status"] = "ok"
    result["volume"] = volume
    return result


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

    wall_start = time.monotonic()

    completed = 0
    skipped = 0
    total_volume = 0

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_polygon, row, config, copernicus_creds): idx
            for idx, row in gdf.iterrows()
        }

        for future in as_completed(futures):
            try:
                result = future.result()
                if result.get("completed"):
                    completed += 1
                    total_volume += result.get("volume", 0)
                elif result.get("skipped"):
                    skipped += 1
            except Exception:
                logger.exception("Polygon job failed")

    wall_elapsed = time.monotonic() - wall_start
    n_total = len(gdf)
    logger.info(
        "SUMMARY workers=%d jobs_ok=%d skipped=%d/%d wall_time=%.1fs",
        max_workers,
        completed,
        skipped,
        n_total,
        wall_elapsed,
    )
    if completed > 0:
        avg_time = wall_elapsed / completed
        avg_volume = total_volume / completed
        logger.info(
            "DETAIL avg_time=%.1fs/job avg_volume=%.0fpx",
            avg_time,
            avg_volume,
        )

    logger.info("Bronze processing complete for %d polygons", len(gdf))


if __name__ == "__main__":
    main()