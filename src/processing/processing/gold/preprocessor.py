import json
import os
from datetime import datetime, timezone

import xarray as xr

from processing.gold import io

GIT_SHA = os.environ.get("GIT_SHA", "unknown")


def build_record(sidecar: dict, dataset: xr.Dataset) -> dict:
    props = sidecar.get("properties", {})
    objectid = str(props.get("objectid", ""))

    metadata = {
        "git_sha": sidecar.get("processing_silver_metadata", {}).get("git_sha", ""),
        "timestamp": sidecar.get("processing_silver_metadata", {}).get("timestamp", ""),
        "bronze_git_sha": sidecar.get("processing_bronze_metadata", {}).get("git_sha", ""),
        "gold_git_sha": GIT_SHA,
    }

    cultivo = props.get("cultivo", "")

    record = {
        "objectid": objectid,
        "event_time": datetime.now(timezone.utc).isoformat(),
        "cultivo": cultivo,
        "departamen": props.get("departamen", ""),
        "municipio": props.get("municipio", ""),
        "year": _parse_year(props.get("periodo", "")),
        "semester": _parse_semester(props.get("intervalo", "")),
        "metadata": json.dumps(metadata),
    }

    for band in io.LIST_BANDS:
        record[f"{band}_series"] = io.get_series_as_string(dataset, band)

    for idx in io.LIST_INDEXES:
        record[f"{idx}_series"] = io.get_series_as_string(dataset, idx)

    return record


def _parse_year(periodo: str) -> int:
    if periodo:
        parts = periodo.split("-")
        return int(parts[0]) if parts else 0
    return 0


def _parse_semester(intervalo: str) -> int:
    if intervalo:
        low = intervalo.lower().strip()
        if "i" in low or "semestre i" in low:
            return 1
        if "ii" in low or "semestre ii" in low:
            return 2
        digits = "".join(c for c in intervalo if c.isdigit())
        return int(digits) if digits else 1
    return 1


def process_single(sidecar_path: str) -> dict:
    try:
        sidecar = io.load_silver_sidecar(sidecar_path)
        props = sidecar.get("properties", {})
        objectid = str(props.get("objectid", ""))
        zarr_key = sidecar.get("processing_silver_metadata", {}).get("zarr_key", "")
        if zarr_key:
            pid = zarr_key.replace("processed/", "").replace(".zarr", "")
        else:
            pid = f"{props.get('service', 'unknown')}_{props.get('objectid', 'unknown')}"

        if objectid and not io.check_lineage(objectid, GIT_SHA):
            return {"status": "skipped", "objectid": objectid, "pid": pid}

        dataset = io.load_silver_zarr(pid)
        record = build_record(sidecar, dataset)
        return {"status": "ok", "record": record, "pid": pid}
    except Exception as e:
        return {"status": "error", "error": str(e), "path": sidecar_path}