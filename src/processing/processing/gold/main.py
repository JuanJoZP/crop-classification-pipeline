import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from processing.gold import io, stats
from processing.gold.preprocessor import process_single

logger = logging.getLogger(__name__)


def run() -> tuple[int, int]:
    logger.info("Gold processing starting")

    sidecar_paths = io.discover_silver_sidecars()
    total = len(sidecar_paths)

    if total == 0:
        logger.warning("No silver sidecars found, exiting")
        return 0, 0

    io.reset()
    stats.reset()

    wall_start = time.monotonic()
    stop_event = threading.Event()
    metrics_thread = threading.Thread(
        target=stats.log_metrics, args=(stop_event, total), daemon=True
    )
    metrics_thread.start()

    try:
        from tqdm import tqdm

        has_tqdm = True
    except ImportError:
        has_tqdm = False
        logger.warning("tqdm not installed, progress bar disabled")

    success_count = 0
    error_count = 0
    max_workers = io.get_workers()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_single, path): idx for idx, path in enumerate(sidecar_paths)
        }

        if has_tqdm:
            pbar = tqdm(total=total, desc="Gold processing", unit="parcel")
        else:
            pbar = None

        for future in as_completed(futures):
            result = future.result()
            if result and result.get("status") == "ok":
                io.add_to_batch(result["record"])
                success_count += 1
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

    stop_event.set()
    metrics_thread.join(timeout=5)
    io.flush_batch()

    wall_elapsed = time.monotonic() - wall_start
    logger.info(
        "SUMMARY workers=%d success=%d error=%d wall_time=%.1fs rate=%.1f parcels/s",
        max_workers,
        success_count,
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