import json
import requests
import pandas as pd
from datetime import date
from pathlib import Path
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

def fetch_weather(session: requests.Session, lat: float, lon: float) -> dict | None:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "forecast_days": 7,
        "timezone": "auto",
       "daily": ",".join([
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "precipitation_probability_max",
            "wind_speed_10m_max",
            "wind_gusts_10m_max",
            "weather_code",
        ]),
    }
    for attempt in range(1, 4):

        try:
            response = session.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429:
                print("Limit API atteint. Arret du script.")
                raise SystemExit(1)
            return None

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            logger.warning(f"Tentative {attempt}/3 échouée pour ({lat}, {lon})")
            if attempt < 3:
                time.sleep(2 * attempt)
        
        except requests.exceptions.RequestException as e:
            print(f"Failed to fetch coordinates ({lat}, {lon}): {e}")
            return None
    logger.error(f"Abandon pour ({lat}, {lon}) apres 3 tentatives")


def fetch_all_cities(df: pd.DataFrame):
    session = requests.Session()
    Path("bronze").mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()

    for _, row in df.iterrows():
        city_id = row['id']
        city_name = row['city_ascii']
        lat = row['lat']
        lng = row['lng']

        #Fetching weather
        weather_data = fetch_weather(session, lat, lng)
        time.sleep(1)

        output_file = f"bronze/weather_{city_id}_{today}.json"

        if weather_data is not None:
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(weather_data, f, indent=2)
            print(f"{output_file} -> Saved")
        else:
            print(f"{output_file} -> Not Saved & Skipped")

if __name__ == "__main__":
    cities_file = "bronze/cities_raw.csv"

    if Path(cities_file).exists():
        df_cities = pd.read_csv(cities_file)
        fetch_all_cities(df_cities)
    else:
        print(f"File {cities_file} not found.")
    # data = fetch_weather(33.5731, -7.5898)
    # print(data)

            

