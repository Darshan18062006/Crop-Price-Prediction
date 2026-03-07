from flask import Flask, request, jsonify,render_template
from flask_cors import CORS

from predict import predict_price, forecast_prices
# Optional: import data sources if available
try:
    from data_sources.weather_api import get_weather
    from data_sources.agmarknet_api import get_mandi_prices, get_mandi_prices_for_crop
except ImportError:
    get_weather = None
    get_mandi_prices = None
    get_mandi_prices_for_crop = None

app = Flask(__name__, template_folder="../frontend")
CORS(app)

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/result.html")
def result():
    return render_template("result.html")

# ─────────────────────────────────────────
# Predict Price
# ─────────────────────────────────────────
@app.route("/predict", methods=["POST"])
def predict():

    data = request.get_json()

    crop = data.get("crop")
    rainfall = float(data.get("rainfall", 0))
    temperature = float(data.get("temperature", 30))
    humidity = float(data.get("humidity", 60))
    state = data.get("state", None)

    price, source = predict_price(
        crop,
        rainfall,
        temperature,
        humidity,
        state
    )

    if price is None:
        return jsonify({
            "error": "Crop not found in model or live API"
        }), 404

    return jsonify({
        "crop": crop,
        "price": price,
        "source": source
    })


# ─────────────────────────────────────────
# Forecast Prices
# ─────────────────────────────────────────
@app.route("/forecast", methods=["POST"])
def forecast():

    data = request.get_json()

    crop = data.get("crop")
    rainfall = float(data.get("rainfall", 0))
    temperature = float(data.get("temperature", 30))
    humidity = float(data.get("humidity", 60))
    days = int(data.get("days", 30))
    state = data.get("state", None)

    prices, source = forecast_prices(
        crop,
        rainfall,
        temperature,
        humidity,
        days,
        state
    )

    return jsonify({
        "forecast": prices,
        "source": source
    })


# ─────────────────────────────────────────
# Mandi Prices
# ─────────────────────────────────────────
@app.route("/mandi", methods=["GET"])
def mandi():

    crop = request.args.get("crop", "")
    state = request.args.get("state", "Karnataka")

    if not crop:
        return jsonify({"error": "crop parameter required"}), 400

    if get_mandi_prices_for_crop is None:
        return jsonify({"error": "data_sources module not available"}), 503

    prices = get_mandi_prices_for_crop(
        crop=crop,
        state=state,
        limit=20
    )

    return jsonify({
        "crop": crop,
        "state": state,
        "mandis": prices
    })


# ─────────────────────────────────────────
# AI Sell Recommendation
# ─────────────────────────────────────────
@app.route("/recommend", methods=["POST"])
def recommend():

    data = request.get_json()

    crop = data.get("crop", "Unknown")
    price = float(data.get("price", 0))
    forecast = data.get("forecast", [])

    if not forecast:
        return jsonify({
            "recommendation": {
                "verdict": "SELL NOW",
                "best_sell_window": "Today",
                "expected_price_at_best": price,
                "confidence": "Low",
                "reasons": ["No forecast data available"],
                "risks": [],
                "storage_tip": "Sell soon as forecast unavailable",
                "summary": "Forecast data not available. Selling now is safer."
            }
        })

    min_price = min(forecast)
    max_price = max(forecast)
    avg_price = sum(forecast) / len(forecast)

    peak_day = forecast.index(max_price) + 1
    low_day = forecast.index(min_price) + 1

    change_percent = ((max_price - price) / price) * 100

    # Decision Logic
    if change_percent > 8:
        verdict = "WAIT"
        confidence = "High"
    elif change_percent > 3:
        verdict = "SELL PARTIAL"
        confidence = "Medium"
    else:
        verdict = "SELL NOW"
        confidence = "High"

    recommendation = {
        "verdict": verdict,
        "best_sell_window": f"Day {peak_day}",
        "expected_price_at_best": round(max_price, 2),
        "confidence": confidence,
        "reasons": [
            f"Forecast peak price ₹{max_price:.0f} expected on day {peak_day}",
            f"Current price ₹{price:.0f}",
            f"Average forecast ₹{avg_price:.0f}"
        ],
        "risks": [
            "Weather changes",
            "Market supply fluctuations"
        ],
        "storage_tip": "Store in cool ventilated storage to maintain quality",
        "summary": f"Prices may peak around day {peak_day}. Expected price about ₹{max_price:.0f}/quintal."
    }

    return jsonify({
        "crop": crop,
        "recommendation": recommendation
    })


# ─────────────────────────────────────────
# Combined Data API
# ─────────────────────────────────────────
@app.route("/data")
def data():

    try:
        if get_mandi_prices is None:
            return jsonify({"error": "data_sources module not available"}), 503
        mandi_prices = get_mandi_prices()

        return jsonify({
            "mandi_prices": mandi_prices
        })

    except Exception as e:
        return jsonify({"error": str(e)})


# ─────────────────────────────────────────
# Run Server
# ─────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True)