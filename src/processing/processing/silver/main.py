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
    discover_parcels_from_polygons_key,
    load_bronze_sidecar,
    load_dataset,
    load_silver_sidecar,
    save_dataset,
    upload_silver_sidecar,
)
from processing.silver.parcel import ParcelInfo, parse_parcel_info
from processing.silver.preprocessor import EmptyDatasetError, SilverPreprocessor
from processing.silver.sidecar import build_sidecar, should_process
from processing.silver.split import SubParcel, compute_area_ha, split_polygon

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


def _make_sub_parcel(original: ParcelInfo, sub: SubParcel) -> ParcelInfo:
    pid = f"{original.pid}_{sub.suffix}" if sub.suffix else original.pid
    return ParcelInfo(
        pid=pid,
        cultivo=original.cultivo,
        year=original.year,
        semester=original.semester,
        geometry=sub.geometry_wgs84,
    )


def _modify_sidecar_for_sub(bronze_sidecar: dict, sub: SubParcel) -> dict:
    modified = dict(bronze_sidecar)
    props = dict(bronze_sidecar["properties"])
    if sub.suffix is not None:
        props["objectid"] = f"{props.get('objectid', '')}_{sub.suffix}"
        props["geometry"] = sub.geometry_wgs84
        props["split_area_ha"] = sub.area_ha
        props["split_index"] = sub.suffix
        original_area = compute_area_ha(bronze_sidecar["properties"]["geometry"])
        props["original_area_ha"] = original_area
    modified["properties"] = props
    return modified


def process_parcel(
    bronze_sidecar_key: str, cfg: dict, s3: s3fs_lib.S3FileSystem
):
    global completed, skipped, failed
    original_pid = None
    try:
        bronze_sidecar = load_bronze_sidecar(bronze_sidecar_key)
        parcel = parse_parcel_info(bronze_sidecar)
        original_pid = parcel.pid
        logger.info("Processing parcel %s", original_pid)

        sub_parcels = split_polygon(
            parcel.geometry,
            area_threshold_ha=cfg.get("area_threshold_ha", 10.0),
            cell_size_m=cfg.get("cell_size_m", 223.0),
        )

        is_split = sub_parcels[0].suffix is not None
        if is_split:
            logger.info(
                "Parcel %s split into %d sub-parcels", original_pid, len(sub_parcels)
            )

        subs_to_process: list[tuple[SubParcel, str, ParcelInfo, dict]] = []
        for sub in sub_parcels:
            sub_pid = f"{original_pid}_{sub.suffix}" if sub.suffix else original_pid
            sub_parcel = _make_sub_parcel(parcel, sub)
            modified_bronze = _modify_sidecar_for_sub(bronze_sidecar, sub)

            silver_sidecar = load_silver_sidecar(sub_pid)
            if not should_process(modified_bronze, silver_sidecar, GIT_SHA):
                logger.info("Sub-parcel %s already processed, skipping", sub_pid)
                with completed_lock:
                    skipped += 1
                continue

            subs_to_process.append((sub, sub_pid, sub_parcel, modified_bronze))

        if not subs_to_process:
            logger.info("All sub-parcels of %s already processed", original_pid)
            return

        dataset = load_dataset(original_pid, s3)
        logger.info("Loading dataset into memory for parcel=%s", original_pid)
        dataset = dataset.load()

        any_success = False
        for sub, sub_pid, sub_parcel, modified_bronze in subs_to_process:
            try:
                ds_copy = dataset.copy(deep=True)
                preprocessor = SilverPreprocessor(ds_copy, sub_parcel, cfg)
                preprocessor.preprocess()
                data_key = save_dataset(sub_pid, preprocessor.dataset, s3)

                processing_timestamp = datetime.now(timezone.utc).isoformat()
                silver_sidecar_data = build_sidecar(
                    modified_bronze, processing_timestamp, GIT_SHA, data_key=data_key
                )
                upload_silver_sidecar(sub_pid, silver_sidecar_data)

                any_success = True
                with completed_lock:
                    completed += 1
                logger.info("Sub-parcel %s complete", sub_pid)

            except EmptyDatasetError:
                logger.warning("Sub-parcel %s has no data after preprocessing, skipping", sub_pid)
                with completed_lock:
                    skipped += 1
            except Exception:
                logger.exception("Failed to process sub-parcel %s", sub_pid)
                with completed_lock:
                    failed += 1

    except EmptyDatasetError:
        if original_pid:
            logger.warning("Parcel %s has no data after preprocessing, skipping", original_pid)
        with completed_lock:
            skipped += 1
    except Exception:
        if original_pid:
            logger.exception("Failed to process parcel %s", original_pid)
        with completed_lock:
            failed += 1


def main():
    global completed, skipped, failed
    completed = 0
    skipped = 0
    failed = 0

    cfg = load_config()
    s3 = s3fs_lib.S3FileSystem(anon=False)

    POLYGONS_KEY = os.environ.get("POLYGONS_KEY", "")
    if POLYGONS_KEY:
        sidecar_keys = discover_parcels_from_polygons_key(POLYGONS_KEY, OFFSET, LIMIT)
    else:
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