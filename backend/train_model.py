"""
train_model.py — Train on REAL historical data from data.gov.in Agmarknet API.

Steps:
1. Fetches real historical mandi prices for all crops from data.gov.in (parallel)
2. Joins with real weather data from Open-Meteo (cached per state)
3. Trains Random Forest on actual price patterns
4. Saves model

Run: python backend/train_model.py
"""
import os, pickle, time, requests
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_PATH  = os.path.join(BASE_DIR, "data", "dataset.csv")
MODEL_PATH = os.path.join(BASE_DIR, "models", "model.pkl")

API_KEY     = os.environ.get("DATA_GOV_API_KEY", "")
RESOURCE_ID = "9ef84268-d588-465a-a308-a864a43d0070"
BASE_URL    = "https://api.data.gov.in/resource/" + RESOURCE_ID

CROPS = [
    "Tomato", "Onion", "Potato", "Brinjal", "Cauliflower", "Cabbage",
    "Okra", "Chilli", "Garlic", "Ginger", "Turmeric", "Cucumber",
    "Pumpkin", "Coriander", "Apple", "Mango", "Banana", "Papaya",
    "Pomegranate", "Grapes", "Orange", "Lemon", "Guava", "Watermelon",
    "Rice", "Wheat", "Bajra", "Maize", "Jowar",
    "Arhar Dal", "Moong Dal", "Urad Dal", "Chana", "Masoor Dal",
    "Soybean", "Groundnut", "Mustard", "Cotton", "Sugarcane",
]

STATE_COORDS = {
    "Karnataka":       (12.97, 77.59),
    "Maharashtra":     (19.07, 72.88),
    "Andhra Pradesh":  (17.38, 78.49),
    "Tamil Nadu":      (13.08, 80.27),
    "Uttar Pradesh":   (26.85, 80.95),
    "Punjab":          (30.73, 76.78),
    "Himachal Pradesh":(31.10, 77.17),
    "Rajasthan":       (26.91, 75.79),
    "Gujarat":         (23.02, 72.57),
    "West Bengal":     (22.57, 88.36),
}

# ── In-memory weather cache (avoids re-fetching same state) ──────────────
_weather_cache: dict = {}


def get_weather_for_state(state: str) -> dict:
    """Cached weather fetch — only hits API once per unique state."""
    if state in _weather_cache:
        return _weather_cache[state]

    lat, lon = STATE_COORDS.get(state, (20.59, 78.96))
    try:
        url = (f"https://api.open-meteo.com/v1/forecast"
               f"?latitude={lat}&longitude={lon}"
               f"&current=temperature_2m,relative_humidity_2m,precipitation"
               f"&timezone=Asia/Kolkata")
        r   = requests.get(url, timeout=5)   # reduced from no timeout → 5s
        cur = r.json().get("current", {})
        result = {
            "temperature": cur.get("temperature_2m", 28),
            "humidity":    cur.get("relative_humidity_2m", 65),
            "rainfall":    cur.get("precipitation", 0),
        }
    except:
        result = {"temperature": 28, "humidity": 65, "rainfall": 5}

    _weather_cache[state] = result
    return result


def fetch_real_prices(crop: str, limit: int = 100) -> list:
    """Fetch real historical mandi records for a crop from data.gov.in"""
    if not API_KEY:
        return []
    params = {
        "api-key":            API_KEY,
        "format":             "json",
        "limit":              limit,
        "filters[commodity]": crop,
    }
    try:
        r = requests.get(BASE_URL, params=params, timeout=10)
        r.raise_for_status()
        return r.json().get("records", [])
    except Exception as e:
        print(f"  ⚠ API error for {crop}: {e}")
        return []


def fetch_crop_rows(crop: str) -> list[dict]:
    """
    Fetch mandi records + weather for one crop.
    Designed to run in a thread pool.
    """
    records = fetch_real_prices(crop, limit=100)
    if not records:
        return []

    states    = [r.get("state", "Karnataka") for r in records]
    top_state = max(set(states), key=states.count)
    weather   = get_weather_for_state(top_state)   # cached — no duplicate HTTP calls

    rows = []
    for rec in records:
        try:
            modal_price = float(rec.get("modal_price", 0))
            if modal_price <= 0:
                continue
            rows.append({
                "crop":        crop,
                "modal_price": modal_price,
                "min_price":   float(rec.get("min_price", modal_price)),
                "max_price":   float(rec.get("max_price", modal_price)),
                "state":       rec.get("state", ""),
                "market":      rec.get("market", ""),
                "temperature": weather["temperature"],
                "humidity":    weather["humidity"],
                "rainfall":    weather["rainfall"],
            })
        except:
            continue
    return rows


def build_real_dataset() -> pd.DataFrame:
    """
    Fetch all crops IN PARALLEL using a thread pool.
    ~8-10x faster than sequential fetching.
    """
    all_rows = []
    print(f"\nFetching real mandi data for {len(CROPS)} crops (parallel)...\n")

    # Use up to 10 threads — safe for I/O-bound HTTP requests
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_crop = {executor.submit(fetch_crop_rows, crop): crop for crop in CROPS}
        for future in as_completed(future_to_crop):
            crop = future_to_crop[future]
            try:
                rows = future.result()
                count = len(rows)
                all_rows.extend(rows)
                print(f"  ✓ {crop}: {count} records")
            except Exception as e:
                print(f"  ✗ {crop}: {e}")

    return pd.DataFrame(all_rows)


def train():
    os.makedirs(os.path.dirname(DATA_PATH),  exist_ok=True)
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)

    if not API_KEY:
        print("ERROR: DATA_GOV_API_KEY not set.")
        print("Set it with: $env:DATA_GOV_API_KEY='your_key_here'")
        print("Then run: python backend/train_model.py")
        return

    t0 = time.time()
    df = build_real_dataset()
    print(f"\n⏱ Data fetch completed in {time.time()-t0:.1f}s")

    if df.empty or len(df) < 20:
        print("\nERROR: Not enough real data fetched. Check your API key and internet.")
        return

    print(f"\nTotal real records fetched: {len(df)}")
    print(f"Crops with data: {df['crop'].nunique()}")
    print(f"\nPrice ranges from real data:")
    print(df.groupby("crop")["modal_price"].agg(["mean","min","max"]).round(0).to_string())

    df.to_csv(DATA_PATH, index=False)
    print(f"\nDataset saved → {DATA_PATH}")

    le = LabelEncoder()
    df["crop_encoded"] = le.fit_transform(df["crop"])

    X = df[["crop_encoded", "rainfall", "temperature", "humidity"]]
    y = df["modal_price"]
    X.columns = ["crop", "rainfall", "temperature", "humidity"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    print(f"\nTraining on {len(X_train)} rows, testing on {len(X_test)} rows...")
    model = RandomForestRegressor(n_estimators=300, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    mae   = mean_absolute_error(y_test, preds)
    r2    = r2_score(y_test, preds)
    print(f"\n── Model Performance ──")
    print(f"  MAE  : ₹{mae:.0f}/quintal")
    print(f"  R²   : {r2:.3f}")

    with open(MODEL_PATH, "wb") as f:
        pickle.dump({"model": model, "encoder": le}, f)
    print(f"\n✅ Model saved → {MODEL_PATH}")

    print(f"\n── Real Price Sanity Check ──")
    for crop in df["crop"].unique()[:10]:
        enc      = int(le.transform([crop])[0])
        inp      = pd.DataFrame([[enc, 5, 28, 65]], columns=["crop","rainfall","temperature","humidity"])
        pred     = round(float(model.predict(inp)[0]), 0)
        real_avg = round(df[df["crop"]==crop]["modal_price"].mean(), 0)
        diff     = abs(pred - real_avg) / real_avg * 100
        status   = "✅" if diff < 25 else "⚠️"
        print(f"  {status} {crop:15} predicted ₹{pred:,.0f}  |  real avg ₹{real_avg:,.0f}")


if __name__ == "__main__":
    train()