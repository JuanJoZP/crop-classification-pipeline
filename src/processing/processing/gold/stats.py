import logging
import threading

import psutil

logger = logging.getLogger(__name__)

METRICS_INTERVAL = int(__import__("os").environ.get("METRICS_INTERVAL", "30"))

_completed = 0
_completed_lock = threading.Lock()


def increment_completed(n: int = 1):
    global _completed
    with _completed_lock:
        _completed += n


def get_completed() -> int:
    with _completed_lock:
        return _completed


def log_metrics(stop_event: threading.Event, total: int):
    process = psutil.Process()
    from processing.gold import io as gold_io

    while not stop_event.is_set():
        cpu = process.cpu_percent(interval=None)
        mem = process.memory_info()
        net_io = psutil.net_io_counters()
        done = get_completed()
        queued = gold_io.get_queue_size()
        ingested = gold_io.get_ingested_count()
        logger.info(
            "METRICS cpu=%.1f%% mem_rss=%.0fMB net_sent=%.0fMB net_recv=%.0fMB progress=%d/%d queued=%d ingested=%d",
            cpu,
            mem.rss / 1024 / 1024,
            net_io.bytes_sent / 1024 / 1024,
            net_io.bytes_recv / 1024 / 1024,
            done,
            total,
            queued,
            ingested,
        )
        stop_event.wait(METRICS_INTERVAL)


def reset():
    global _completed
    with _completed_lock:
        _completed = 0
