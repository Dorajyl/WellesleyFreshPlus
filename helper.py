import datetime
from datetime import date, datetime, timedelta
import requests

AVI_API = "https://dish.avifoodsystems.com/api/menu-items/week"

# Dining hall + meal IDs from your earlier code
DINING_HALLS = {
        95: {  # Bates
            "name": "Bates",
            "meals": {
                "Breakfast": 145,
                "Lunch": 146,
                "Dinner": 311,
            },
        },
        131: {  # Stone D
            "name": "Stone D",
            "meals": {
                "Breakfast": 261,
                "Lunch": 262,
                "Dinner": 263,
            },
        },
        96: {  # Lulu
            "name": "Lulu",
            "meals": {
                "Breakfast": 148,
                "Lunch": 149,
                "Dinner": 312,
            },
        },
        97: {  # Tower
            "name": "Tower",
            "meals": {
                "Breakfast": 153,
                "Lunch": 154,
                "Dinner": 310,
            },
        },
    }
MEALS = ["Breakfast", "Lunch", "Dinner"]


def get_meal_order(now: datetime) -> list[str]:
    """Reorder Breakfast/Lunch/Dinner so the 'current' meal shows first."""
    h = now.hour
    if h < 10:
        return ["Breakfast", "Lunch", "Dinner"]
    elif h < 15:
        return ["Lunch", "Dinner", "Breakfast"]
    else:
        return ["Dinner", "Breakfast", "Lunch"]


def fetch_menu_for(d: date, dhall_id: int, meal_name: str) -> list[dict]:
    """Call AVI API and return a list of dishes for that hall/meal *on that day*."""
    meal_id = DINING_HALLS[dhall_id]["meals"][meal_name]

    resp = requests.get(
        AVI_API,
        params={
            "date": d.strftime("%-m/%-d/%y"),  # e.g. '11/15/25'
            "locationId": dhall_id,
            "mealId": meal_id,
        },
        verify=False,
        timeout=5,
    )
    resp.raise_for_status()
    data = resp.json() or []

    target_iso = d.isoformat()  # '2025-11-15'
    dishes: list[dict] = []

    for dish in data:
        # The API returns a full week; each item has its own date. Filter here.
        dish_date_raw = (dish.get("date") or "")[:10]  # '2025-11-15T00:00:00' → '2025-11-15'
        if dish_date_raw != target_iso:
            continue

        dishes.append(
            {
                "did": dish.get("id"),
                "name": dish.get("name"),
                "station": dish.get("stationName"),
            }
        )

    return dishes