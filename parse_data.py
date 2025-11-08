import pandas as pd 
import json
import requests
import cs304dbi as dbi
from datetime import date

def _to_int(x):
    try:
        if x is None or x == "": 
            return None
        return int(float(x))
    except Exception:
        return None
def _to_float(x):
    try:
        if x is None or x == "":
            return None
        return float(x)
    except Exception:
        return None
def build_payload_df(data, dhall: str, meal: str) -> pd.DataFrame:
    rows = []
    for dish in data:
        nutr = dish.get("nutritionals", {}) or {}

        # build row with safe casting and presence checks
        row = {
            # basic dish details
            "did": _to_int(dish.get("id")),
            "date": (dish.get("date") or "")[:10],
            "dhall": dhall,
            "meal": meal,
            "name": dish.get("name"),
            "description": dish.get("description"),
            # station details
            "station": (dish.get("stationName") or "").title(),
            "stationOrder": _to_int(dish.get("stationOrder")),
            # serving size
            "serving_size": _to_float(nutr.get("servingSize")),
            "serving_size_unit": nutr.get("servingSizeUOM"),
            # nutritionals
            "calories": _to_int(nutr.get("calories")),
            "fat": _to_int(nutr.get("fat")),                       # g
            "calories_from_fat": _to_int(nutr.get("caloriesFromFat")), # not in Wellesley Fresh
            "saturated_fat": _to_int(nutr.get("saturatedFat")),    # g
            "trans_fat": _to_int(nutr.get("transFat")),            # g
            "cholesterol": _to_int(nutr.get("cholesterol")),       # mg
            "sodium": _to_int(nutr.get("sodium")),                 # mg
            "carbohydrates": _to_int(nutr.get("carbohydrates")),   # g
            "dietary_fiber": _to_int(nutr.get("dietaryFiber")),    # g
            "sugars": _to_int(nutr.get("sugars")),                 # g
            "added_sugar": _to_int(nutr.get("addedSugar")),        # g
            "protein": _to_int(nutr.get("protein")),               # g
        }

        # optional: flatten preferences / allergens into semicolon-separated strings
        prefs = dish.get("preferences") or []
        alerg = dish.get("allergens") or []
        row["preferences"] = "; ".join([str(p.get("name")) for p in prefs if isinstance(p, dict)])
        row["allergens"]   = "; ".join([str(a.get("name")) for a in alerg if isinstance(a, dict)])

        rows.append(row)

    df = pd.DataFrame(rows)

    # types: make 'date' a datetime (keeps date only)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date

    return df

AVI_API = "https://dish.avifoodsystems.com/api/menu-items/week"
date = date.today()
response = requests.get(
        AVI_API,
        params={
            "date": date.strftime(
                "%-m/%-d/%y"  # the - makes the date not 0-padded
            ),
            "locationId": 96, # Lulu
            "mealId": 312, # Dinner
        },
        verify=False,
    )
data = response.json()
df = build_payload_df(data, "Lulu", "Dinner")

dbi.conf('wfresh_db')
conn = dbi.connect()
cur = conn.cursor()
cols = ["did", "name", "description"] 
rows = list(df[cols].itertuples(index=False, name=None))
sql = "INSERT IGNORE INTO dish (did,name,description) VALUES (%s, %s, %s)"  # MySQL param style
cur.executemany(sql, rows)
conn.commit()