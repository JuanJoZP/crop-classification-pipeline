import logging
from dataclasses import dataclass
from typing import Optional

from pyproj import CRS, Transformer
from shapely.geometry import box, mapping, shape
from shapely.ops import transform

logger = logging.getLogger(__name__)

DEFAULT_AREA_THRESHOLD_HA = 10.0
DEFAULT_CELL_SIZE_M = 223.0
MIN_SUB_PARCEL_HA = 0.5


@dataclass
class SubParcel:
    suffix: Optional[int]
    geometry_wgs84: dict
    area_ha: float


def _utm_epsg(lon: float) -> int:
    zone = int((lon + 180) / 6) + 1
    return 32600 + zone


def compute_area_ha(geometry_wgs84: dict) -> float:
    geom = shape(geometry_wgs84)
    epsg = _utm_epsg(geom.centroid.x)
    fwd = Transformer.from_crs(
        CRS.from_epsg(4326), CRS.from_epsg(epsg), always_xy=True
    ).transform
    geom_utm = transform(fwd, geom)
    return geom_utm.area / 10_000.0


def split_polygon(
    geometry_wgs84: dict,
    area_threshold_ha: float = DEFAULT_AREA_THRESHOLD_HA,
    cell_size_m: float = DEFAULT_CELL_SIZE_M,
    min_sub_parcel_ha: float = MIN_SUB_PARCEL_HA,
) -> list[SubParcel]:
    area_ha = compute_area_ha(geometry_wgs84)

    if area_ha <= area_threshold_ha:
        logger.info(
            "Polygon area %.1f ha <= threshold %.1f ha, no split",
            area_ha,
            area_threshold_ha,
        )
        return [SubParcel(suffix=None, geometry_wgs84=geometry_wgs84, area_ha=area_ha)]

    geom = shape(geometry_wgs84)
    epsg = _utm_epsg(geom.centroid.x)

    fwd = Transformer.from_crs(
        CRS.from_epsg(4326), CRS.from_epsg(epsg), always_xy=True
    ).transform
    rev = Transformer.from_crs(
        CRS.from_epsg(epsg), CRS.from_epsg(4326), always_xy=True
    ).transform
    geom_utm = transform(fwd, geom)
    minx, miny, maxx, maxy = geom_utm.bounds

    sub_parcels: list[SubParcel] = []
    suffix = 1
    x = minx
    while x < maxx:
        y = miny
        while y < maxy:
            cell = box(x, y, x + cell_size_m, y + cell_size_m)
            intersection = geom_utm.intersection(cell)

            if intersection.is_empty or intersection.area < 1.0:
                y += cell_size_m
                continue

            intersection_ha = intersection.area / 10_000.0
            if intersection_ha < min_sub_parcel_ha:
                y += cell_size_m
                continue

            intersection_wgs84 = transform(rev, intersection)
            sub_parcels.append(
                SubParcel(
                    suffix=suffix,
                    geometry_wgs84=mapping(intersection_wgs84),
                    area_ha=intersection_ha,
                )
            )
            suffix += 1
            y += cell_size_m
        x += cell_size_m

    logger.info(
        "Split polygon (area=%.1f ha) into %d sub-parcels (cell=%.0fx%.0fm)",
        area_ha,
        len(sub_parcels),
        cell_size_m,
        cell_size_m,
    )
    return sub_parcels
