import json
from typing import Any, Dict

from endpoints.crawl_polygons import handle as crawl_polygons
from endpoints.list_municipalities import handle as list_municipalities

ROUTERS = {
    "crawl_polygons": crawl_polygons,
    "list_municipalities": list_municipalities,
}


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    action = event.get("action", "crawl_polygons")

    route = ROUTERS.get(action)
    if route is None:
        return {
            "statusCode": 400,
            "body": json.dumps(
                {
                    "error": f"Unknown action: '{action}'.",
                    "available_actions": list(ROUTERS.keys()),
                }
            ),
        }

    try:
        return route(event)
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }
