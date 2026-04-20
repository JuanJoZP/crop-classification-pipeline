import logging
import os

import boto3

SSM_PREFIX = os.environ.get("SSM_PREFIX", "/crop-classification")

logger = logging.getLogger(__name__)
_ssm_client = None


def _get_ssm_client():
    global _ssm_client
    if _ssm_client is None:
        kwargs = {}
        region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
        if region:
            kwargs["region_name"] = region
        _ssm_client = boto3.client("ssm", **kwargs)
    return _ssm_client


def _get_param(name: str, decrypt: bool = False) -> str:
    ssm = _get_ssm_client()
    return ssm.get_parameter(Name=f"{SSM_PREFIX}/{name}", WithDecryption=decrypt)[
        "Parameter"
    ]["Value"]


def get_copernicus_creds() -> dict:
    logger.info("Fetching Copernicus credentials from SSM")
    return {
        "endpoint": _get_param("copernicus/s3_endpoint"),
        "access_key": _get_param("copernicus/s3_access_key", decrypt=True),
        "secret_key": _get_param("copernicus/s3_secret_key", decrypt=True),
    }


def load_config() -> dict:
    logger.info("Fetching bronze config from SSM")
    bands_raw = _get_param("bronze/bands")
    return {
        "catalog": {
            "url": _get_param("bronze/catalog_url"),
            "collection": "sentinel-2-l2a",
            "s2_processing_baseline_min": _get_param(
                "bronze/s2_processing_baseline_min"
            ),
        },
        "sentinel2_l2a": {
            "bands": [b.strip() for b in bands_raw.split(",")],
            "resolution": float(_get_param("bronze/resolution")),
            "crs": _get_param("bronze/crs"),
            "dtype": _get_param("bronze/dtype"),
        },
        "max_cloud_cover": float(_get_param("bronze/max_cloud_cover")),
        "workers": int(os.environ.get("WORKERS", _get_param("bronze/workers"))),
    }
