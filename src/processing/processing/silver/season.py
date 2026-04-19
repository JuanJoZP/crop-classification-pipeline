import logging
from typing import List, Tuple

import numpy as np
import pandas as pd
import xarray as xr
from scipy.signal import find_peaks

from processing.silver.parcel import ParcelInfo, PAPA_VARIETY, normalize_crop

logger = logging.getLogger(__name__)


class MainSeasonFilter:
    def __init__(self, init_prominence: float | None = None, max_recursion: int = 10):
        self.init_prominence = init_prominence
        self.max_recursion = max_recursion

    def filter_season(self, dataset: xr.Dataset, parcel: ParcelInfo) -> xr.Dataset:
        variety = normalize_crop(parcel.cultivo)
        if variety == PAPA_VARIETY:
            logger.info("Parcel %s is papa, filtering main season", parcel.pid)
            dataset, _ = self._filter_main_season(dataset, parcel)
            return dataset

        target_year = parcel.year
        if parcel.semester == 1:
            sem_start = pd.Timestamp(target_year, 1, 1)
            sem_end = pd.Timestamp(target_year, 6, 30)
        else:
            sem_start = pd.Timestamp(target_year, 7, 1)
            sem_end = pd.Timestamp(target_year, 12, 31)
        dataset = dataset.where(
            (dataset.time >= sem_start) & (dataset.time <= sem_end)
        )
        return dataset

    def _filter_main_season(
        self,
        dataset: xr.Dataset,
        parcel: ParcelInfo,
        prominence: float | None = None,
        depth: int = 0,
    ) -> Tuple[xr.Dataset, bool]:
        if prominence is None:
            prominence = self.init_prominence if self.init_prominence is not None else 0.1

        seasons = self._get_seasons(dataset, prominence)
        season_start, season_end = self._get_main_season(seasons, parcel)

        if season_start is np.datetime64("NaT") or season_end is np.datetime64("NaT"):
            logger.warning(
                "No valid season found for parcel=%s, falling back to full year",
                parcel.pid,
            )
            target_year = parcel.year
            sem_start = pd.Timestamp(target_year, 1, 1)
            sem_end = pd.Timestamp(target_year, 12, 31)
            dataset = dataset.where(
                (dataset.time >= sem_start) & (dataset.time <= sem_end)
            )
            return dataset, True

        months_diff = int(
            season_end.astype("datetime64[M]").astype(int)
            - season_start.astype("datetime64[M]").astype(int)
        )

        dataset = dataset.where(
            (dataset.time >= season_start) & (dataset.time <= season_end)
        )

        if months_diff > 8 and depth < self.max_recursion:
            return self._filter_main_season(dataset, parcel, prominence / 2, depth + 1)

        return dataset, True

    @staticmethod
    def _get_seasons(
        dataset: xr.Dataset, prominence: float
    ) -> List[Tuple[np.datetime64, np.datetime64]]:
        serie = dataset["veg_index"].mean(dim=["pixel"])

        diff = serie.diff("time")
        inc_mask = diff > 0
        consecutive = inc_mask.rolling(time=2).sum()
        valid_idx = np.where(consecutive >= 2)[0]

        if len(valid_idx) > 0 and valid_idx[0] > 0:
            start_idx = valid_idx[0] - 1
            serie = serie.isel(time=slice(start_idx, None))

        serie_invertida = -serie
        valles_indices, _ = find_peaks(
            serie_invertida.to_numpy(), prominence=prominence
        )

        times = pd.to_datetime(serie.time.values)
        seasons: List[Tuple[np.datetime64, np.datetime64]] = []

        if len(valles_indices) == 0:
            seasons.append((np.datetime64(times[0]), np.datetime64(times[-1])))
            return seasons

        prev_idx = 0
        for v_idx in valles_indices:
            start_time = np.datetime64(times[prev_idx])
            end_time = np.datetime64(times[v_idx])
            seasons.append((start_time, end_time))
            prev_idx = v_idx

        if prev_idx < len(times) - 1:
            seasons.append((np.datetime64(times[prev_idx]), np.datetime64(times[-1])))

        return seasons

    @staticmethod
    def _get_main_season(
        seasons: List[Tuple[np.datetime64, np.datetime64]],
        parcel: ParcelInfo,
    ) -> Tuple[np.datetime64, np.datetime64]:
        if not seasons:
            return np.datetime64("NaT"), np.datetime64("NaT")

        target_year = parcel.year
        if parcel.semester == 1:
            sem_start = pd.Timestamp(target_year, 1, 1)
            sem_center = pd.Timestamp(target_year, 3, 15)
            sem_end = pd.Timestamp(target_year, 6, 30)
        else:
            sem_start = pd.Timestamp(target_year, 7, 1)
            sem_center = pd.Timestamp(target_year, 9, 15)
            sem_end = pd.Timestamp(target_year, 12, 31)

        def is_valid(season: Tuple[np.datetime64, np.datetime64]) -> bool:
            start, end = pd.to_datetime(season[0]), pd.to_datetime(season[1])
            duration_days = (end - start).days
            return duration_days >= 4 * 30.44

        def overlap_days(season: Tuple[np.datetime64, np.datetime64]) -> int:
            start, end = pd.to_datetime(season[0]), pd.to_datetime(season[1])
            overlap_start = max(start, sem_start)
            overlap_end = min(end, sem_end)
            if overlap_start <= overlap_end:
                return (overlap_end - overlap_start).days + 1
            return 0

        def _season_end(season: Tuple[np.datetime64, np.datetime64]) -> pd.Timestamp:
            start, end = pd.to_datetime(season[0]), pd.to_datetime(season[1])
            return start + (end - start) / 2

        valid_seasons = [s for s in seasons if is_valid(s)]
        if not valid_seasons:
            return np.datetime64("NaT"), np.datetime64("NaT")

        candidates = [
            s
            for s in valid_seasons
            if (pd.to_datetime(s[0]).year == target_year)
            or (pd.to_datetime(s[1]).year == target_year)
        ]

        if not candidates:
            candidates = valid_seasons

        ranked = sorted(
            candidates,
            key=lambda s: (
                overlap_days(s),
                -abs((_season_end(s) - sem_center).days),
            ),
            reverse=True,
        )

        best = ranked[0]
        start, end = best
        return np.datetime64(start), np.datetime64(end)