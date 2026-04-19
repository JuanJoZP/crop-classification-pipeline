import logging

import xarray as xr

from processing.silver.phenolopy import calc_phenometrics, smooth

logger = logging.getLogger(__name__)

MIN_TIME_STEPS = 5


class PhenolopyCalculator:
    def __init__(
        self,
        peak_metric: str = "pos",
        base_metric: str = "vos",
        method: str = "seasonal_amplitude",
        factor: float = 0.2,
        thresh_sides: str = "two_sided",
        abs_value: float = 0.1,
        smooth_method: str = "savitsky",
        smooth_window_length: int = 3,
        smooth_polyorder: int = 1,
        smooth_sigma: int = 1,
    ):
        self.peak_metric = peak_metric
        self.base_metric = base_metric
        self.method = method
        self.factor = factor
        self.thresh_sides = thresh_sides
        self.abs_value = abs_value
        self.smooth_method = smooth_method
        self.smooth_window_length = smooth_window_length
        self.smooth_polyorder = smooth_polyorder
        self.smooth_sigma = smooth_sigma

    def calculate(self, dataset: xr.Dataset) -> xr.Dataset:
        n_time = dataset.sizes.get("time", 0)
        if n_time < MIN_TIME_STEPS:
            logger.warning(
                "Skipping phenometrics: only %d time steps (minimum %d)",
                n_time,
                MIN_TIME_STEPS,
            )
            return xr.Dataset()

        window_length = min(self.smooth_window_length, n_time)
        polyorder = min(self.smooth_polyorder, window_length - 1)

        logger.info("Smoothing veg_index for phenometrics")
        smoothed = smooth(
            dataset,
            method=self.smooth_method,
            window_length=window_length,
            polyorder=polyorder,
            sigma=self.smooth_sigma,
        )

        logger.info("Calculating phenometrics")
        phenometrics = calc_phenometrics(
            smoothed["veg_index"],
            peak_metric=self.peak_metric,
            base_metric=self.base_metric,
            method=self.method,
            factor=self.factor,
            thresh_sides=self.thresh_sides,
            abs_value=self.abs_value,
        )
        return phenometrics