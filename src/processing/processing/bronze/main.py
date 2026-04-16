import json
import os

S3_BUCKET = os.environ.get("S3_BUCKET", "crop-classification-data")
STAC_CATALOG_URL = os.environ.get(
    "STAC_CATALOG_URL", "https://earth-search.aws.element84.com/v1"
)


def main():
    polygons_json = os.environ.get("POLYGONS")
    if polygons_json:
        polygons = json.loads(polygons_json)
    else:
        raise NotImplementedError("POLYGONS env var not provided")

    raise NotImplementedError("Bronze processing not yet implemented")


if __name__ == "__main__":
    main()
