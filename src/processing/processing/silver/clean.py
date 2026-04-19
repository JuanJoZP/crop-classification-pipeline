import logging

import xarray as xr

from processing.silver.phenolopy import remove_outliers

logger = logging.getLogger(__name__)


class PhenolopyCleaner:
    def __init__(self, resample_freq: str = "1ME", outlier_method: str = "median"):
        self.resample_freq = resample_freq
        self.outlier_method = outlier_method

    def clean(self, dataset: xr.Dataset) -> xr.Dataset:
        logger.info("Cleaning dataset: remove_outliers + resample + interpolate")
        clean = remove_outliers(dataset, method=self.outlier_method)
        clean = clean.resample(time=self.resample_freq).mean("time")
        clean = clean.interpolate_na(dim="time", method="linear")
        return clean