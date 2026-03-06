import os
import pandas as pd

from backend.data_sources.agmarknet_api import get_mandi_prices
from backend.data_sources.weather_api import get_weather

# Use absolute path so it works from any directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "dataset.csv")


def build_dataset():
    mandi_data = get_mandi_prices()
    weather = get_weather()

    rows = []

    for record in mandi_data:
        row = {
            "crop": record.get("commodity"),
            "price": float(record.get("modal_price", 0)),
            "temperature": weather.get("temperature", 30),
            "rainfall": weather.get("rainfall", 0),
            "humidity": weather.get("humidity", 60),
        }
        rows.append(row)

    df = pd.DataFrame(rows)

    # Ensure output directory exists
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    df.to_csv(DATA_PATH, index=False)

    print(f"Dataset saved to: {DATA_PATH}")
    return df


if __name__ == "__main__":
    dataset = build_dataset()
    print("Dataset created successfully\n")
    print(dataset.head())