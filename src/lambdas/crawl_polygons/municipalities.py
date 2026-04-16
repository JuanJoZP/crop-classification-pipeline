import os
from pathlib import Path
from typing import List, Optional, Set

MUNICIPALITIES_DEFAULT_DIR = str(Path(__file__).parent / "municipalities")
MUNICIPALITIES_CACHE_DIR = os.environ.get(
    "MUNICIPALITIES_CACHE_DIR", MUNICIPALITIES_DEFAULT_DIR
)


def _load_municipalities_from_file(crop: str) -> Optional[Set[str]]:
    cache_path = Path(MUNICIPALITIES_CACHE_DIR) / f"{crop.lower()}.json"
    if not cache_path.exists():
        return None
    import json

    entries = json.loads(cache_path.read_text(encoding="utf-8"))
    return {entry["municipio"] for entry in entries}


def validate_municipalities(
    municipalities: List[str], crop: Optional[str] = None
) -> Optional[List[str]]:
    valid_set: Optional[Set[str]] = None
    if crop:
        valid_set = _load_municipalities_from_file(crop)
    if valid_set is None:
        cache_path = Path(MUNICIPALITIES_CACHE_DIR) / "papa.json"
        if cache_path.exists():
            import json

            entries = json.loads(cache_path.read_text(encoding="utf-8"))
            valid_set = {entry["municipio"] for entry in entries}
    if valid_set is None:
        return None
    invalid = [m for m in municipalities if m not in valid_set]
    return invalid if invalid else None
