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


def _get_param(name: str, default: str = "") -> str:
    ssm = _get_ssm_client()
    try:
        return ssm.get_parameter(Name=f"{SSM_PREFIX}/{name}", WithDecryption=False)[
            "Parameter"
        ]["Value"]
    except ssm.exceptions.ParameterNotFound:
        return default


def load_config() -> dict:
    logger.info("Fetching gold config from SSM")
    return {
        "workers": int(_get_param("gold/workers", "10")),
    }