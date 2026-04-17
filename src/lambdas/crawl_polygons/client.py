import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

UPRA_BASE_URL = os.environ.get(
    "UPRA_GEOSERVICIOS_URL",
    "https://geoservicios.upra.gov.co/arcgis/rest/services",
)
UPRA_SERVICE_PREFIX = "MonitoreoCultivos"
MUNICIPALITIES_CACHE_DIR = os.environ.get(
    "MUNICIPALITIES_CACHE_DIR",
    "/tmp/municipalities",
)

CropConfig = Dict[str, Any]
CROP_CONFIGS: Dict[str, CropConfig] = {
    "arroz": {"type": "semester", "suffixes": ("s1", "s2")},
    "maiz": {"type": "semester", "suffixes": ("1", "2")},
    "papa": {"type": "semester", "suffixes": ("s1", "s2")},
    "Cacao": {"type": "annual"},
    "maranon": {"type": "annual"},
    "palma": {"type": "annual"},
    "Pastos": {"type": "annual"},
    "musaceas": {"type": "annual"},
}

VALID_PERIODS: Dict[str, List[str]] = {
    "2020": ["Cacao_2020", "maranon_2020", "palma_2020", "Pastos_2020"],
    "2021": [
        "arroz_2021_s1",
        "arroz_2021_s2",
        "maiz_2021_1",
        "maiz_2021_2",
        "papa_2021_s1",
        "papa_2021_s2",
        "Cacao_2021",
        "maranon_2021",
        "palma_2021",
        "Pastos_2021",
    ],
    "2022": [
        "arroz_2022_s1",
        "arroz_2022_s2",
        "maiz_2022_1",
        "maiz_2022_2",
        "papa_2022_s1",
        "papa_2022_s2",
        "Cacao_2022",
        "maranon_2022",
        "palma_2022",
        "Pastos_2022",
    ],
    "2023": [
        "arroz_2023_s1",
        "arroz_2023_s2",
        "maiz_2023_1",
        "maiz_2023_2",
        "papa_2023_s1",
        "papa_2023_s2",
        "Cacao_2023",
        "musaceas_2023",
    ],
    "2024": ["arroz_2024_s1", "papa_2024_s1"],
}

OUT_FIELDS = "objectid,cultivo,municipio,departamen,periodo,intervalo"


def validate_periods(periodos: List[str]) -> List[str]:
    return [p for p in periodos if p not in VALID_PERIODS]


def build_services_for_period(periodo: str) -> List[str]:
    return VALID_PERIODS.get(periodo, [])


def query_service(municipality: str, service: str) -> List[Dict[str, Any]]:
    url = f"{UPRA_BASE_URL}/{UPRA_SERVICE_PREFIX}/{service}/MapServer/0/query"
    params = {
        "where": f"municipio='{municipality}'",
        "outFields": OUT_FIELDS,
        "f": "geojson",
        "outSR": "4326",
    }
    response = httpx.get(url, params=params, timeout=30.0)
    response.raise_for_status()
    data = response.json()
    features = data.get("features", [])
    acquisition_date = datetime.now(timezone.utc).isoformat()
    results = []
    for feature in features:
        props = feature.get("properties") or {}
        row = {
            **props,
            "geometry": feature.get("geometry"),
            "service": service,
            "acquisition_date": acquisition_date,
        }
        results.append(row)
    return results


def fetch_polygons(
    municipalities: List[str], periodos: List[str]
) -> List[Dict[str, Any]]:
    services_cache: Dict[str, List[str]] = {}
    all_rows: List[Dict[str, Any]] = []

    for periodo in periodos:
        year = str(periodo)
        if year not in services_cache:
            services_cache[year] = build_services_for_period(year)
        for municipality in municipalities:
            for service in services_cache[year]:
                rows = query_service(municipality, service)
                all_rows.extend(rows)

    return all_rows


def rows_to_geojson(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    features = []
    for row in rows:
        geometry = row.pop("geometry")
        features.append(
            {
                "type": "Feature",
                "geometry": geometry,
                "properties": row,
            }
        )
    return {
        "type": "FeatureCollection",
        "features": features,
        "count": len(features),
    }


SUPPORTED_CROPS: List[str] = sorted(CROP_CONFIGS.keys())


def _get_services_for_crop(crop: str, periods: Optional[List[str]] = None) -> List[str]:
    services: List[str] = []
    target_periods = periods or sorted(VALID_PERIODS.keys())
    for periodo in target_periods:
        for service in VALID_PERIODS.get(periodo, []):
            if service.lower().startswith(crop.lower()):
                services.append(service)
    return services


def _query_distinct_municipalities(service: str) -> List[Dict[str, str]]:
    url = f"{UPRA_BASE_URL}/{UPRA_SERVICE_PREFIX}/{service}/MapServer/0/query"
    params = {
        "where": "1=1",
        "outFields": "municipio,departamen",
        "returnDistinctValues": "true",
        "returnGeometry": "false",
        "f": "json",
    }
    response = httpx.get(url, params=params, timeout=30.0)
    response.raise_for_status()
    data = response.json()
    return [feature["attributes"] for feature in data.get("features", [])]


def fetch_municipalities(
    crop: str, periods: Optional[List[str]] = None
) -> List[Dict[str, str]]:
    cache_path = Path(MUNICIPALITIES_CACHE_DIR) / f"{crop.lower()}.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    services = _get_services_for_crop(crop, periods)
    if not services:
        raise ValueError(
            f"No services found for crop '{crop}'. SUPPORTED_CROPS: {SUPPORTED_CROPS}"
        )

    seen: set = set()
    municipalities: List[Dict[str, str]] = []
    for service in services:
        entries = _query_distinct_municipalities(service)
        for entry in entries:
            key = (entry.get("municipio", ""), entry.get("departamen", ""))
            if key not in seen:
                seen.add(key)
                municipalities.append(
                    {
                        "municipio": entry.get("municipio", ""),
                        "departamen": entry.get("departamen", ""),
                    }
                )

    municipalities.sort(key=lambda m: (m["departamen"], m["municipio"]))
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(municipalities, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return municipalities
