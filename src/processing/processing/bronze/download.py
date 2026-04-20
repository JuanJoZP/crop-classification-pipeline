import logging
import os
from collections import defaultdict

import numpy as np
import odc.stac
import pystac_client
import s3fs
import xarray as xr
from tqdm import tqdm

from processing.bronze.config import load_config

logger = logging.getLogger(__name__)

ANNUAL_CROPS = {"Cacao", "maranon", "palma", "Pastos", "musaceas"}
SEMESTER_CROPS = {"arroz", "maiz", "papa"}


def _time_range(cultivo: str, periodo: str) -> tuple[str, str]:
    parts = periodo.split("_")
    crop = parts[0]
    year = int(parts[1])
    if crop in ANNUAL_CROPS:
        return f"{year}-01-01", f"{year}-12-31"
    semester = parts[2]
    if semester in ("s1", "1"):
        return f"{year - 1}-06-01", f"{year}-09-01"
    return f"{year}-01-01", f"{year + 1}-03-01"


def _filter_by_cloud_cover(items, max_cloud_cover: float):
    groups: dict = defaultdict(list)
    for item in items:
        groups[item.datetime].append(item)

    def mean_cc_valid(group):
        return (
            np.mean([i.properties["eo:cloud_cover"] for i in group]) <= max_cloud_cover
        )

    return [item for group in groups.values() if mean_cc_valid(group) for item in group]


def search_items(
    geometry, cultivo: str, periodo: str, max_cloud_cover: float, config: dict
):
    time_from, time_to = _time_range(cultivo, periodo)
    datetime_range = f"{time_from}/{time_to}"

    catalog = pystac_client.Client.open(config["catalog"]["url"])
    search = catalog.search(
        collections=[config["catalog"]["collection"]],
        bbox=geometry.bounds,
        datetime=datetime_range,
        query={
            "s2:processing_baseline": {
                "gte": config["catalog"]["s2_processing_baseline_min"]
            }
        },
        sortby=["properties.datetime"],
    )
    items = list(search.items())
    logger.info("Found %d items before cloud filter", len(items))
    items = _filter_by_cloud_cover(items, max_cloud_cover)
    logger.info(
        "Found %d items after cloud filter (max %.0f%%)", len(items), max_cloud_cover
    )
    return items


def write_zarr(pid: str, dataset: xr.Dataset, s3: s3fs.S3FileSystem):
    s3_bucket = os.environ["S3_BUCKET"]
    raw_prefix = os.environ.get("RAW_PREFIX", "raw")
    zarr_path = f"s3://{s3_bucket}/{raw_prefix}/{pid}.zarr"

    logger.info("Writing zarr for %s to %s", pid, zarr_path)
    if s3.exists(zarr_path):
        logger.info("Removing existing zarr at %s", zarr_path)
        s3.rm(zarr_path, recursive=True)
    store = s3fs.S3Map(root=zarr_path, s3=s3, check=False)
    dataset.to_zarr(store, consolidated=True)
    logger.info("Written zarr for %s", pid)
    return f"{raw_prefix}/{pid}.zarr"


def download_polygon(
    pid: str,
    row,
    config: dict,
    copernicus_creds: dict,
    s3: s3fs.S3FileSystem,
) -> tuple:
    geometry = row.geometry
    cultivo = row["cultivo"]
    periodo = row["service"]
    max_cloud_cover = config["max_cloud_cover"]

    items = search_items(geometry, cultivo, periodo, max_cloud_cover, config)
    if not items:
        logger.warning("No items for %s, skipping", pid)
        return None, 0

    odc.stac.configure_rio(
        aws={
            "endpoint_url": copernicus_creds["endpoint"],
            "aws_access_key_id": copernicus_creds["access_key"],
            "aws_secret_access_key": copernicus_creds["secret_key"],
            "region_name": "default",
        },
        AWS_VIRTUAL_HOSTING=False,
    )

    dataset = odc.stac.load(
        items,
        bands=config["sentinel2_l2a"]["bands"],
        bbox=geometry.bounds,
        crs=config["sentinel2_l2a"]["crs"],
        resolution=config["sentinel2_l2a"]["resolution"],
        dtype=config["sentinel2_l2a"]["dtype"],
        chunks={},
        progress=tqdm,
    )
    logger.info("Loaded dataset for %s: %s", pid, dataset)

    volume = (
        dataset.dims.get("time", 1)
        * dataset.dims.get("longitude", 1)
        * dataset.dims.get("latitude", 1)
    )
    return write_zarr(pid, dataset, s3), volume
