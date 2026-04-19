import functools
import operator
import logging
from collections.abc import Iterable

import numpy as np
import xarray as xr
from rasterio.features import rasterize
from scipy.ndimage import binary_erosion
from shapely.geometry import shape

import rioxarray  # noqa: F401

logger = logging.getLogger(__name__)


def aoi_mask(
    dataset: xr.Dataset, geometry: dict, padding: int
) -> xr.DataArray:
    geom = shape(geometry)
    mask = rasterize(
        [(geom, 1)],
        out_shape=(len(dataset.latitude), len(dataset.longitude)),
        transform=dataset.rio.transform(),
        fill=0,
        dtype="uint8",
    )

    if padding > 0:
        mask = binary_erosion(mask, iterations=padding).astype(mask.dtype)

    return xr.DataArray(
        mask,
        coords=[dataset.latitude, dataset.longitude],
        dims=["latitude", "longitude"],
        name="aoi",
    )


def clear_pixels_mask(
    dataset: xr.Dataset, padding: int, keep_classes: Iterable[int]
) -> xr.DataArray:
    if "scl" not in dataset.data_vars:
        raise ValueError(
            "SCL band not in dataset. Cannot generate clear pixels mask."
        )

    clear_classes = {4, 5}.union(set(keep_classes))
    masks = dataset.scl.isin(list(clear_classes))

    if padding <= 0:
        return masks

    values = masks.transpose("time", "latitude", "longitude").values
    eroded = np.empty_like(values)

    for t in range(eroded.shape[0]):
        if values[t].all():
            eroded[t] = values[t]
        else:
            eroded[t] = binary_erosion(values[t], iterations=padding).astype(
                masks.dtype
            )

    return xr.DataArray(
        eroded,
        coords=[dataset.time, dataset.latitude, dataset.longitude],
        dims=["time", "latitude", "longitude"],
        name="clear_pixels",
    )


def mask_dataset(
    dataset: xr.Dataset, *masks: xr.DataArray
) -> xr.DataArray:
    if not masks:
        raise ValueError("At least one mask is required.")
    combined = functools.reduce(operator.and_, masks)
    return dataset.where(combined)