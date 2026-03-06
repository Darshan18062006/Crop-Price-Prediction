import requests


def get_weather():
    """
    Fetch current weather for Bengaluru from Open-Meteo API.
    Returns temperature, humidity, and rainfall (precipitation).
    """
    url = (
        "https://api.open-meteo.com/v1/forecast"
        "?latitude=12.97&longitude=77.59"
        "&current=temperature_2m,relative_humidity_2m,precipitation"
        "&timezone=Asia%2FKolkata"
    )

    try:
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        data = r.json()

        current = data.get("current", {})

        return {
            "temperature": current.get("temperature_2m", 30),
            "humidity": current.get("relative_humidity_2m", 60),
            "rainfall": current.get("precipitation", 0)
        }

    except Exception as e:
        print(f"Weather API error: {e}. Using fallback values.")
        return {
            "temperature": 30,
            "humidity": 60,
            "rainfall": 5
        }