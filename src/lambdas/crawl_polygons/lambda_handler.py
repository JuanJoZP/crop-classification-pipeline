import json
import os

import httpx

UPRA_GEOSERVICIOS_URL = os.environ["UPRA_GEOSERVICIOS_URL"]


def handler(event, context):
    try:
        polygons = _fetch_polygons(event)
        return {
            "statusCode": 200,
            "body": json.dumps({"polygons": polygons}),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }


def _fetch_polygons(event):
    raise NotImplementedError("UPRA API integration pending")
