from dataclasses import dataclass

PAPA_VARIETY = "papa"


@dataclass
class ParcelInfo:
    pid: str
    cultivo: str
    year: int
    semester: int
    geometry: dict


def parse_parcel_info(sidecar: dict) -> ParcelInfo:
    props = sidecar["properties"]
    service = props["service"]
    pid = sidecar.get("processing_bronze_metadata", {}).get("zarr_key", "")
    if pid:
        pid = pid.replace("raw/", "").replace(".zarr", "")
    else:
        pid = f"{service}_{props.get('objectid', 'unknown')}"

    parts = service.split("_")
    year = int(parts[1]) if len(parts) > 1 else 0
    semester_str = parts[2] if len(parts) > 2 else "s1"
    semester = int(semester_str.replace("s", ""))

    return ParcelInfo(
        pid=pid,
        cultivo=props["cultivo"],
        year=year,
        semester=semester,
        geometry=props["geometry"],
    )


def normalize_crop(cultivo: str) -> str:
    return cultivo.lower().strip()
