import logging
from typing import Protocol

import xarray as xr

from processing.silver.clean import PhenolopyCleaner
from processing.silver.indexes import register as indexes_register
from processing.silver.masks import aoi_mask, clear_pixels_mask, mask_dataset
from processing.silver.parcel import PAPA_VARIETY, ParcelInfo, normalize_crop
from processing.silver.phenometrics import PhenolopyCalculator
from processing.silver.season import MainSeasonFilter

logger = logging.getLogger(__name__)

BAND_NAMES_MAPPING = {"swir16": "swir1"}

MIN_PIXELS = 1
MIN_TIMESTEPS = 1


class EmptyDatasetError(Exception):
    pass


class Cleaner(Protocol):
    def clean(self, dataset: xr.Dataset) -> xr.Dataset: ...


class SeasonFilter(Protocol):
    def filter_season(self, dataset: xr.Dataset, parcel: ParcelInfo) -> xr.Dataset: ...


class PhenometricsCalculator(Protocol):
    def calculate(self, dataset: xr.Dataset) -> xr.Dataset: ...


class SilverPreprocessor:
    def __init__(
        self,
        dataset: xr.Dataset,
        parcel: ParcelInfo,
        cfg: dict,
        cleaner: Cleaner | None = None,
        season_filter: SeasonFilter | None = None,
        phenometrics_calc: PhenometricsCalculator | None = None,
    ):
        self.dataset = dataset
        self.parcel = parcel
        self.cfg = cfg
        self.is_clean = False
        self.is_masked = False
        self.is_filtered = False
        self._cleaner = cleaner if cleaner is not None else PhenolopyCleaner()
        self._season_filter = season_filter if season_filter is not None else MainSeasonFilter()
        self._phenometrics_calc = phenometrics_calc if phenometrics_calc is not None else PhenolopyCalculator()

    def _check_not_empty(self, stage: str) -> None:
        n_pixels = self.dataset.sizes.get("pixel", 0)
        n_time = self.dataset.sizes.get("time", 0)
        if n_pixels < MIN_PIXELS:
            raise EmptyDatasetError(
                f"After {stage}: 0 pixels remaining for parcel={self.parcel.pid}"
            )
        if n_time < MIN_TIMESTEPS:
            raise EmptyDatasetError(
                f"After {stage}: 0 time steps remaining for parcel={self.parcel.pid}"
            )

    def preprocess(self) -> None:
        pid = self.parcel.pid
        logger.info("Preprocess start for parcel=%s", pid)

        self.dataset = self.dataset.rename(
            {k: v for k, v in BAND_NAMES_MAPPING.items() if k in self.dataset.data_vars}
        )

        self.dataset["veg_index"] = (self.dataset.nir - self.dataset.red) / (
            self.dataset.nir + self.dataset.red + self.dataset.swir1
        )

        logger.info("Masking dataset for parcel=%s", pid)
        aoi = aoi_mask(
            self.dataset, self.parcel.geometry, self.cfg["aoi_padding"]
        )
        clear = clear_pixels_mask(
            self.dataset,
            self.cfg["clouds_padding"],
            self.cfg["cloud_mask_scl_keep_classes"],
        )
        self.dataset = mask_dataset(self.dataset, aoi, clear)
        self.is_masked = True

        self.dataset = self.dataset.stack(
            pixel=("latitude", "longitude"), create_index=False
        )
        self.dataset = self.dataset.dropna(
            dim="pixel", how="all", subset=["veg_index"]
        )
        self._check_not_empty("mask+stack")

        logger.info("Cleaning dataset for parcel=%s", pid)
        self._clean()
        self._check_not_empty("clean")

        logger.info("Filtering time range for parcel=%s", pid)
        self._filter_season()

        self.dataset = self.dataset.dropna(
            dim="time", how="all", subset=["veg_index"]
        )
        self._check_not_empty("filter_season")

        logger.info("Calculating spectral indexes for parcel=%s", pid)
        self._calc_indexes()

        if self.cfg.get("calc_phenometrics"):
            logger.info("Calculating phenometrics for parcel=%s", pid)
            self._calc_phenometrics()

        drop_vars = [v for v in ["spatial_ref", "scl"] if v in self.dataset.data_vars]
        self.dataset = self.dataset.drop_vars(drop_vars).transpose("pixel", "time")
        logger.info("Preprocess finished for parcel=%s", pid)

    def _clean(self) -> None:
        if not self.is_masked:
            raise ValueError("Dataset must be masked before cleaning.")
        self.dataset = self._cleaner.clean(self.dataset)
        self.is_clean = True

    def _filter_season(self) -> None:
        if not self.is_clean:
            raise ValueError("Dataset must be cleaned before filtering season.")
        self.dataset = self._season_filter.filter_season(self.dataset, self.parcel)
        self.is_filtered = True

    def _calc_indexes(self) -> None:
        for index_name in self.cfg.get("indexes", []):
            if index_name in indexes_register:
                self.dataset[index_name] = indexes_register[index_name](self.dataset)
            else:
                logger.warning("Unknown spectral index: %s", index_name)

    def _calc_phenometrics(self) -> None:
        result = self._phenometrics_calc.calculate(self.dataset)
        if result is not None and len(result.data_vars) > 0:
            self.dataset = xr.merge([self.dataset, result])