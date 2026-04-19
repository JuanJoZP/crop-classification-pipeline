import json
import logging
import os
import tempfile
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import s3fs as s3fs_lib
from sklearn.preprocessing import MinMaxScaler, StandardScaler

logger = logging.getLogger(__name__)


def parse_parcel_id(sidecar: dict) -> str:
    props = sidecar["properties"]
    service = props["service"]
    silver_meta = sidecar.get("processing_silver_metadata", {})
    zarr_key = silver_meta.get("zarr_key", "")
    if zarr_key:
        return zarr_key.replace("processed/", "").replace(".zarr", "")
    bronze_meta = sidecar.get("processing_bronze_metadata", {})
    zarr_key = bronze_meta.get("zarr_key", "")
    if zarr_key:
        return zarr_key.replace("raw/", "").replace(".zarr", "")
    return f"{service}_{props.get('objectid', 'unknown')}"


def check_linaje(silver_sidecar: dict, gold_metadata: dict, current_sha: str) -> bool:
    if gold_metadata is None:
        return True

    stored_silver_sha = silver_sidecar.get("processing_silver_metadata", {}).get("git_sha", "")
    stored_bronze_sha = silver_sidecar.get("processing_bronze_metadata", {}).get("git_sha", "")

    if gold_metadata.get("gold_git_sha") != current_sha:
        return True
    if gold_metadata.get("linaje", {}).get("silver_git_sha") != stored_silver_sha:
        return True
    if gold_metadata.get("linaje", {}).get("bronze_git_sha") != stored_bronze_sha:
        return True

    return False


def yield_parcels(sidecar_keys: list[str], s3_bucket: str, processed_prefix: str):
    s3 = s3fs_lib.S3FileSystem(anon=False)
    for key in sidecar_keys:
        sidecar = json.loads(
            s3fs_lib.S3FileSystem(anon=False).cat(f"s3://{s3_bucket}/{key}")
        )
        pid = parse_parcel_id(sidecar)
        zarr_path = f"s3://{s3_bucket}/{processed_prefix}/{pid}.zarr"
        try:
            store = s3fs_lib.S3Map(root=zarr_path, s3=s3, check=False)
            import xarray as xr
            ds = xr.open_zarr(store, consolidated=True).load()
            yield pid, ds, sidecar
        except Exception as e:
            logger.warning("Failed to load %s: %s", zarr_path, e)
            continue


def compute_global_scalers(sidecar_keys: list[str], s3_bucket: str, processed_prefix: str, exclude: list[str], method: str = "zscore"):
    logger.info("Computing global %s scalers from %d parcels", method, len(sidecar_keys))

    all_values = {}

    for pid, ds, _ in yield_parcels(sidecar_keys, s3_bucket, processed_prefix):
        for var in ds.data_vars:
            if var in exclude:
                continue
            if "pixel" in ds[var].dims and "time" in ds[var].dims:
                mean_ts = ds[var].mean(dim="pixel").values
                if var not in all_values:
                    all_values[var] = []
                all_values[var].extend(mean_ts.tolist())

    scalers = {}
    for var, values in all_values.items():
        arr = np.array(values).reshape(-1, 1)
        if method == "minmax":
            scaler = MinMaxScaler()
            scaler.fit(arr)
            scalers[var] = scaler
            logger.info("Scaler for %s: min=%.2f, max=%.2f", var, scaler.data_min_[0], scaler.data_max_[0])
        else:
            scaler = StandardScaler()
            scaler.fit(arr)
            scalers[var] = scaler
            logger.info("Scaler for %s: mean=%.2f, std=%.2f", var, scaler.mean_[0], scaler.scale_[0])

    return scalers


def serialize_scaler(scaler, method: str) -> dict:
    if method == "minmax":
        return {
            "min": float(scaler.data_min_[0]),
            "max": float(scaler.data_max_[0]),
        }
    return {
        "mean": float(scaler.mean_[0]),
        "std": float(scaler.scale_[0]),
    }


def process_parcels(sidecar_keys: list[str], s3_bucket: str, processed_prefix: str, fitted_scalers: dict, exclude: list[str]):
    records = []
    for pid, ds, sidecar in yield_parcels(sidecar_keys, s3_bucket, processed_prefix):
        n_time = ds.sizes.get("time", 0)
        n_pix = ds.sizes.get("pixel", 0)
        if n_time == 0 or n_pix == 0:
            continue

        props = sidecar["properties"]
        service = props["service"]
        parts = service.split("_")
        year = int(parts[1]) if len(parts) > 1 else 0
        semester = int(parts[2].replace("s", "")) if len(parts) > 2 else 1

        cultivo = props.get("cultivo", "unknown")
        label = {"arroz": 0, "papa": 1, "maiz": 2}.get(cultivo.lower().strip(), -1)

        record = {
            "polygon_id": pid,
            "cultivo": cultivo,
            "departamen": props.get("departamen", ""),
            "municipio": props.get("municipio", ""),
            "year": year,
            "semester": semester,
            "label": label,
            "n_timesteps": n_time,
            "n_pixels": n_pix,
        }

        for var in ds.data_vars:
            if var in exclude:
                continue
            if "pixel" in ds[var].dims and "time" in ds[var].dims:
                mean_ts = ds[var].mean(dim="pixel").values.reshape(-1, 1)
                norm_ts = fitted_scalers[var].transform(mean_ts).flatten()
                record[f"{var}_normalized"] = norm_ts.tolist()

        records.append(record)

    return records


def write_parquet(records: list[dict], path: str):
    df = pd.DataFrame(records)
    df.to_parquet(path, index=False)
    logger.info("Wrote %d records to %s", len(records), path)