import json
import logging
import os
import tempfile
from datetime import datetime, timezone

from processing.gold import io, preprocessor
from processing.gold.config import load_config

S3_BUCKET = os.environ["S3_BUCKET"]
PROCESSED_PREFIX = os.environ.get("PROCESSED_PREFIX", "processed")
OUTPUT_PREFIX = os.environ.get("OUTPUT_PREFIX", "feature-store")

logger = logging.getLogger(__name__)


def main():
    cfg = load_config()
    method = cfg.get("normalization_method", "zscore")
    git_sha = os.environ.get("GIT_SHA", "unknown")

    io.init(S3_BUCKET, OUTPUT_PREFIX)

    silver_keys = io.discover_silver_parcels(PROCESSED_PREFIX)
    exclude = ["spatial_ref", "scl"]

    gold_metadata = io.load_gold_metadata()
    if gold_metadata and not preprocessor.check_linaje(
        io.load_silver_sidecar(silver_keys[0]), gold_metadata, git_sha
    ):
        logger.info("No linaje changes detected, skipping gold processing")
        return

    scalers = preprocessor.compute_global_scalers(
        silver_keys, S3_BUCKET, PROCESSED_PREFIX, exclude, method
    )
    fitted_scalers = scalers

    records = preprocessor.process_parcels(
        silver_keys, S3_BUCKET, PROCESSED_PREFIX, fitted_scalers, exclude
    )

    batch_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    base_name = f"gold_timeseries_{batch_id}"
    parquet_key = f"{OUTPUT_PREFIX}/{base_name}.parquet"

    silver_sample = io.load_silver_sidecar(silver_keys[0])
    silver_sha = silver_sample.get("processing_silver_metadata", {}).get("git_sha", "")
    bronze_sha = silver_sample.get("processing_bronze_metadata", {}).get("git_sha", "")

    metadata = {
        "gold_git_sha": git_sha,
        "gold_timestamp": datetime.now(timezone.utc).isoformat(),
        "parquet_key": parquet_key,
        "n_parcels": len(records),
        "linaje": {
            "bronze_git_sha": bronze_sha,
            "silver_git_sha": silver_sha,
        },
        "scalers": {
            var: preprocessor.serialize_scaler(fitted_scalers[var], method)
            for var in fitted_scalers
        },
        "normalization_method": method,
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        local_parquet = os.path.join(tmpdir, f"{base_name}.parquet")
        preprocessor.write_parquet(records, local_parquet)
        io.upload_file(local_parquet, parquet_key)

        local_meta = os.path.join(tmpdir, f"{base_name}_metadata.json")
        with open(local_meta, "w") as f:
            json.dump(metadata, f, indent=2)
        io.upload_file(local_meta, f"{OUTPUT_PREFIX}/{base_name}_metadata.json")

    logger.info("Gold complete: %d parcels, parquet=%s", len(records), parquet_key)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
