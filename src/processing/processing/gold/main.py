import logging
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

from processing.gold import io, stats
from processing.gold.preprocessor import process_single

S3_BUCKET = os.environ["S3_BUCKET"]
GIT_SHA = os.environ.get("GIT_SHA", "unknown")

logger = logging.getLogger(__name__)


def run() -> tuple[int, int]:
    logger.info("Gold processing starting")

    sidecar_paths = io.discover_silver_from_polygons_key()
    total = len(sidecar_paths)

    if total == 0:
        logger.warning("No silver datasets found, exiting")
        return 0, 0

    objectids = []
    sidecar_data = []
    for data_key in sidecar_paths:
        try:
            sidecar = io.load_silver_sidecar(data_key)
            props = sidecar.get("properties", {})
            objectid = str(props.get("objectid", ""))
            objectids.append(objectid)
            sidecar_data.append((data_key, objectid, sidecar))
        except Exception:
            sidecar_data.append((data_key, "", None))

    logger.info("Checking lineage via Athena for %d objectids", len(objectids))
    lineage_cache = io.check_lineage_athena(objectids, GIT_SHA)
    logger.info("Lineage check: %d already processed, %d to process",
                sum(1 for v in lineage_cache.values() if v),
                sum(1 for v in lineage_cache.values() if not v))

    io.reset()
    stats.reset()

    wall_start = time.monotonic()

    try:
        from tqdm import tqdm
        has_tqdm = True
    except ImportError:
        has_tqdm = False
        logger.warning("tqdm not installed, progress bar disabled")

    success_count = 0
    error_count = 0
    skip_count = 0
    results = []
    max_workers = io.get_workers()

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_single, path, lineage_cache): idx
            for idx, (path, objectid, sidecar) in enumerate(sidecar_data)
        }

        if has_tqdm:
            pbar = tqdm(total=total, desc="Gold processing", unit="parcel")
        else:
            pbar = None

        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            status = result.get("status") if result else "error"

            if status == "ok":
                io.add_to_batch(result["record"])
                success_count += 1
            elif status == "skipped":
                skip_count += 1
            else:
                error_count += 1
                logger.error("Failed: %s", result.get("error", "unknown"))

            stats.increment_completed()

            if pbar:
                pbar.update(1)
                pbar.set_postfix(
                    ingested=io.get_ingested_count(),
                    queued=io.get_queue_size(),
                )

        if pbar:
            pbar.close()
    io.flush_batch()

    wall_elapsed = time.monotonic() - wall_start
    logger.info(
        "SUMMARY workers=%d success=%d skipped=%d error=%d wall_time=%.1fs rate=%.1f parcels/s",
        max_workers,
        success_count,
        skip_count,
        error_count,
        wall_elapsed,
        success_count / wall_elapsed if wall_elapsed > 0 else 0,
    )

    return success_count, error_count


def main():
    success, error = run()
    logger.info("Gold complete: %d success, %d errors", success, error)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(threadName)s %(message)s",
    )
    main()