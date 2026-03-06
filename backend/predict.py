import os, pickle, requests
import numpy as np
import pandas as pd

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "models", "model.pkl")

model   = None
encoder = None

API_KEY     = os.environ.get("DATA_GOV_API_KEY", "")
RESOURCE_ID = "9ef84268-d588-465a-a308-a864a43d0070"
BASE_URL    = "https://api.data.gov.in/resource/" + RESOURCE_ID


# ── Model loading ─────────────────────────────────────────────────────────

def load_model():
    global model, encoder
    if model is None:
        with open(MODEL_PATH, "rb") as f:
            saved = pickle.load(f)
        if isinstance(saved, dict):
            model   = saved["model"]
            encoder = saved.get("encoder")
        else:
            model   = saved
            encoder = None
    return model


def get_model_features():
    m = load_model()
    if hasattr(m, "feature_names_in_"):
        return list(m.feature_names_in_)
    return None


def encode_crop(crop: str):
    """Returns encoded int if crop is known, else None."""
    load_model()
    if encoder is None:
        return None
    if crop in encoder.classes_:
        return int(encoder.transform([crop])[0])
    for known in encoder.classes_:
        if known.lower() == crop.lower():
            return int(encoder.transform([known])[0])
    for known in encoder.classes_:
        if known.lower() in crop.lower() or crop.lower() in known.lower():
            print(f"  Partial match: '{crop}' → '{known}'")
            return int(encoder.transform([known])[0])
    return None   # truly unknown


# ── Live Agmarknet price fetch for unknown crops ──────────────────────────

def fetch_live_price(crop: str, state: str = None) -> float | None:
    """
    Fetch today's modal price directly from Agmarknet for any crop.
    Used when crop is not in the trained model.
    Returns average modal price across records, or None if not found.
    """
    if not API_KEY:
        return None

    params = {
        "api-key":            API_KEY,
        "format":             "json",
        "limit":              50,
        "filters[commodity]": crop,
    }
    if state:
        params["filters[state]"] = state

    try:
        r       = requests.get(BASE_URL, params=params, timeout=6)
        records = r.json().get("records", [])

        prices = []
        for rec in records:
            try:
                p = float(rec.get("modal_price", 0))
                if p > 0:
                    prices.append(p)
            except:
                continue

        if prices:
            avg = sum(prices) / len(prices)
            print(f"  Live fetch for '{crop}': {len(prices)} records, avg ₹{avg:.0f}")
            return round(avg, 2)

    except Exception as e:
        print(f"  Live fetch error for '{crop}': {e}")

    return None


# ── Main prediction ───────────────────────────────────────────────────────

def predict_price(crop, rainfall, temperature, humidity, state=None):
    """
    Predict price for any crop:
    - If crop is in trained model → use ML model
    - If crop is unknown → fetch live price from Agmarknet API
    - If API also fails → return None so caller can show error
    """
    crop_value = encode_crop(crop)

    # ── Known crop: use ML model ──
    if crop_value is not None:
        m        = load_model()
        input_data = pd.DataFrame(
            [[crop_value, rainfall, temperature, humidity]],
            columns=["crop","rainfall","temperature","humidity"]
        )
        return round(float(m.predict(input_data)[0]), 2), "model"

    # ── Unknown crop: fetch live from Agmarknet ──
    print(f"  '{crop}' not in model — fetching live from Agmarknet...")
    live_price = fetch_live_price(crop, state=state)

    if live_price:
        return live_price, "live"

    # ── Complete fallback: use real average Indian mandi prices ──
    FALLBACK_PRICES = {
        # Vegetables (₹/quintal)
        "tomato":      1200, "onion":       800,  "potato":      600,
        "brinjal":     1000, "cauliflower": 1400, "cabbage":     600,
        "okra":        1800, "chilli":      8000, "garlic":      6000,
        "ginger":      5000, "turmeric":    7000, "cucumber":    900,
        "pumpkin":     500,  "coriander":   3000, "capsicum":    2000,
        "carrot":      1200, "radish":      400,  "spinach":     800,
        "bitter gourd":1500, "bottle gourd":600,  "drumstick":   2500,
        "beetroot":    800,  "sweet potato":700,  "yam":         1000,
        # Fruits (₹/quintal)
        "apple":       6000, "mango":       3000, "banana":      1500,
        "papaya":      800,  "pomegranate": 8000, "grapes":      4000,
        "orange":      2500, "lemon":       4000, "guava":       1800,
        "watermelon":  400,  "muskmelon":   600,  "pineapple":   2000,
        "sapota":      2000, "jackfruit":   1000, "fig":         5000,
        # Cereals & Pulses (₹/quintal)
        "rice":        1800, "wheat":       2100, "bajra":       1600,
        "maize":       1400, "jowar":       1500, "ragi":        1700,
        "barley":      1600,
        "arhar dal":   7000, "tur dal":     7000, "moong dal":   7500,
        "urad dal":    6500, "chana":       5000, "masoor dal":  5500,
        "rajma":       9000, "lobia":       5000,
        # Oilseeds & Cash Crops (₹/quintal)
        "soybean":     3800, "groundnut":   5500, "mustard":     5000,
        "sunflower":   4500, "cotton":      6500, "sugarcane":   350,
        "sesame":      8000, "linseed":     5500,
    }

    crop_lower = crop.lower().strip()

    # Exact match
    if crop_lower in FALLBACK_PRICES:
        p = FALLBACK_PRICES[crop_lower]
        print(f"  Using fallback price for '{crop}': ₹{p}")
        return float(p), "fallback"

    # Partial match
    for key, val in FALLBACK_PRICES.items():
        if key in crop_lower or crop_lower in key:
            print(f"  Fallback partial match: '{crop}' → '{key}' ₹{val}")
            return float(val), "fallback"

    return None, "unknown"


def forecast_prices(crop, rainfall, temperature, humidity, days=30, state=None):
    result, source = predict_price(crop, rainfall, temperature, humidity, state)

    if result is None:
        return [], source

    base_price = result
    prices     = [base_price]
    for _ in range(1, days):
        change    = np.random.uniform(-0.04, 0.04)
        drift     = np.random.uniform(-0.005, 0.005)
        new_price = max(prices[-1] * (1 + change + drift), base_price * 0.70)
        prices.append(round(new_price, 2))

    return prices, source