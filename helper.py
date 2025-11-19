import datetime
from datetime import date, datetime, timedelta
import requests
import json
import os

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


def get_cache_filepath():
    """Return the path to the menu cache file."""
    # Store cache in the same directory as helper.py
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'menu_cache.json')


def is_cache_valid(cache_data: dict) -> bool:
    """Check if cache is still valid (not older than 1 day)."""
    if not cache_data or 'cached_date' not in cache_data:
        return False
    
    cached_date_str = cache_data['cached_date']
    try:
        cached_date = datetime.fromisoformat(cached_date_str).date()
        today = date.today()
        # Cache is valid if it's from today or yesterday (to handle late night/early morning edge cases)
        return (today - cached_date).days <= 1
    except (ValueError, TypeError):
        return False


def load_menu_cache() -> dict:
    """Load menu data from cache file if it exists and is valid."""
    cache_file = get_cache_filepath()
    
    if not os.path.exists(cache_file):
        return None
    
    try:
        with open(cache_file, 'r') as f:
            cache_data = json.load(f)
        
        if is_cache_valid(cache_data):
            return cache_data.get('menu_data', None)
        else:
            # Cache is stale, return None to trigger refresh
            return None
    except (json.JSONDecodeError, IOError, KeyError):
        return None


def save_menu_cache(menu_data: dict):
    """Save menu data to cache file."""
    cache_file = get_cache_filepath()
    
    cache_data = {
        'cached_date': datetime.now().isoformat(),
        'menu_data': menu_data
    }
    
    try:
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f, indent=2, default=str)
    except IOError:
        # If we can't write the cache, just continue without it
        pass


def fetch_week_menu(start_date: date = None) -> dict:
    """
    Fetch menu data for a full week starting from start_date (or today if None).
    Returns a dictionary with date strings as keys and menu data as values.
    Uses cache if available and valid.
    """
    if start_date is None:
        start_date = date.today()
    
    # Try to load from cache first
    cached_data = load_menu_cache()
    if cached_data is not None:
        return cached_data
    
    # Cache miss or invalid - fetch fresh data
    week_menu = {}
    
    for offset in range(7):
        d = start_date + timedelta(days=offset)
        date_key = d.isoformat()  # '2025-11-15'
        
        week_menu[date_key] = {}
        
        for meal in MEALS:
            week_menu[date_key][meal] = {}
            for dhall_id, info in DINING_HALLS.items():
                dishes = fetch_menu_for(d, dhall_id, meal)
                if dishes:
                    week_menu[date_key][meal][info["name"]] = dishes
    
    # Save to cache
    save_menu_cache(week_menu)
    
    return week_menu