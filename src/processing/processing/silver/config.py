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


def load_config() -> dict:
    logger.info("Fetching silver config from SSM")
    aoi_padding = float(_get_param("silver/aoi_padding"))
    clouds_padding = float(_get_param("silver/clouds_padding"))
    cloud_mask_scl_keep_classes_raw = _get_param("silver/cloud_mask_scl_keep_classes")
    calc_phenometrics_raw = _get_param("silver/calc_phenometrics")
    indexes_raw = _get_param("silver/indexes")

    return {
        "aoi_padding": aoi_padding,
        "clouds_padding": clouds_padding,
        "cloud_mask_scl_keep_classes": [
            int(c.strip()) for c in cloud_mask_scl_keep_classes_raw.split(",")
        ],
        "calc_phenometrics": calc_phenometrics_raw.lower() in ("true", "1", "yes"),
        "indexes": [i.strip() for i in indexes_raw.split(",")],
    }