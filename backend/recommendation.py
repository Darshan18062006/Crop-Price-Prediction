def recommend_sell(price, forecast):
    """
    Decide when to sell crop based on forecast prices
    """

    if not forecast:
        return {
            "verdict": "SELL NOW",
            "best_sell_window": "Today",
            "expected_price": price,
            "confidence": "Low",
            "reason": "No forecast data available"
        }

    min_price = min(forecast)
    max_price = max(forecast)
    avg_price = sum(forecast) / len(forecast)

    peak_day = forecast.index(max_price) + 1

    # price change %
    change = ((max_price - price) / price) * 100

    if change > 8:
        verdict = "WAIT"
        confidence = "High"
    elif change > 3:
        verdict = "SELL PARTIAL"
        confidence = "Medium"
    else:
        verdict = "SELL NOW"
        confidence = "High"

    return {
        "verdict": verdict,
        "best_sell_window": f"Day {peak_day}",
        "expected_price": round(max_price,2),
        "confidence": confidence,
        "summary": f"Price may reach ₹{max_price} around day {peak_day}"
    }