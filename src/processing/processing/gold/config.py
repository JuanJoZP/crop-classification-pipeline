import logging
import os

import boto3

SSM_PREFIX = os.environ.get("SSM_PREFIX", "/crop-classification")

logger = logging.getLogger(__name__)
_ssm_client = None


def _get_ssm_client():
    global _ssm_client
    if _ssm_client is None:
        _ssm_client = boto3.client("ssm")
    return _ssm_client


def _get_param(name: str, decrypt: bool = False) -> str:
    ssm = _get_ssm_client()
    return ssm.get_parameter(Name=f"{SSM_PREFIX}/{name}", WithDecryption=decrypt)[
        "Parameter"
    ]["Value"]


def load_config() -> dict:
    logger.info("Fetching gold config from SSM")
    return {
        "normalization_method": _get_param("gold/normalization_method"),
        "target_column": _get_param("gold/target_column"),
    }