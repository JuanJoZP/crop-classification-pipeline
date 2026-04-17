import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import s3fs as s3fs_lib
from bronze.config import get_copernicus_creds, load_config
from bronze.download import download_polygon
from bronze.io import load_polygons, upload_sidecar
from bronze.sidecar import build_sidecar, polygon_id

S3_BUCKET = os.environ["S3_BUCKET"]
POLYGONS_KEY = os.environ["POLYGONS_KEY"]
GIT_SHA = os.environ.get("GIT_SHA", "unknown")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def process_polygon(
    row, config: dict, copernicus_creds: dict, s3: s3fs_lib.S3FileSystem
):
    pid = polygon_id(row)
    logger.info("Processing polygon %s", pid)

    zarr_key = download_polygon(pid, row, config, copernicus_creds, s3)
    if zarr_key is None:
        logger.warning("No data for %s, skipping sidecar", pid)
        return

    processing_timestamp = datetime.now(timezone.utc).isoformat()
    sidecar = build_sidecar(row, processing_timestamp, GIT_SHA, POLYGONS_KEY)
    sidecar["processing_metadata"]["zarr_key"] = zarr_key
    upload_sidecar(pid, sidecar)
    logger.info("Polygon %s complete", pid)


def main():
    config = load_config()
    copernicus_creds = get_copernicus_creds()
    gdf = load_polygons(POLYGONS_KEY)
    logger.info("Columns: %s", list(gdf.columns))
    logger.info("CRS: %s", gdf.crs)

    cpu_count = os.cpu_count() or 1
    max_workers = config["workers_per_core"] * cpu_count
    s3 = s3fs_lib.S3FileSystem(anon=False)

    logger.info(
        "Starting bronze processing: %d polygons, %d workers",
        len(gdf),
        max_workers,
    )

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

    logger.info("Bronze processing complete for %d polygons", len(gdf))


if __name__ == "__main__":
    main()
