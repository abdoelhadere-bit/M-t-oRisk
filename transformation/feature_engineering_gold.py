import pandas as pd
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

def categorize_temp(temp_max):
    #later: handle temp < 10
    if temp_max >= 45:
        return "Extreme"
    elif temp_max >= 33:
        return "Chaude"
    elif temp_max >= 20:
        return "Moderee"
    else:
        return "Fraiche"

def categorize_precipitation(prec_mm):
    if prec_mm >= 35:
        return "Forte"
    elif prec_mm >= 15:
        return "Moderee"
    elif prec_mm > 0:
        return "Faible"
    else:
        return "Aucune"

def categorize_wind(gusts_kmh):
    if gusts_kmh >= 90:
        return "Danger"
    elif gusts_kmh >= 30:
        return "Fort"
    else:
        return "Normal"

def categorize_weather_code(code: int) -> str:
    if code == 0:
        return "Ciel degage"
    elif code in [1, 2, 3]:
        return "Nuageux"
    elif code in [45, 48]:
        return "Brouillard"
    elif code in range(51, 68):
        return "Pluie/Bruine"
    elif code in range(71, 87):
        return "Neige"
    elif code in [95, 96, 99]:
        return "Orage"
    else:
        return "Inconnu"
    
def linear_score(value: float, low: float, high: float) -> float:

    if value <= low:
        return 0.0
    if value >= high:
        return 100.0
    return (value - low) / (high - low) * 100

def score_temperature(temp_max: float) -> float:
    return linear_score(temp_max, low=33, high=45)

def score_precipitation(precip_mm: float) -> float:
    return linear_score(precip_mm, low=0, high=35)

def score_wind(gusts_kmh: float) -> float:
    return linear_score(gusts_kmh, low=30, high=80)

def score_weather_code(code: int) -> float:
    codes = {
        0: 0, 1: 5, 2: 10, 3: 15,
        45: 50, 48: 55,
        51: 30, 53: 35, 55: 40, 56: 45, 57: 50,
        61: 40, 63: 55, 65: 70, 66: 60, 67: 75,
        71: 30, 73: 40, 75: 50, 77: 35,
        80: 45, 81: 55, 82: 70,
        85: 45, 86: 60,
        95: 85, 96: 95, 99: 100,
    }
    return codes.get(code, 10)


def calculate_risk_score(row) -> float:
    temp_score = score_temperature(row["temperature_2m_max"])
    precip_score = score_precipitation(row["precipitation_sum"])
    wind_score = score_wind(row["wind_gusts_10m_max"])
    code_score = score_weather_code(row["weather_code"])

    weighted_avg = (wind_score * 0.35 + precip_score * 0.35 + temp_score * 0.15 + code_score * 0.15)

    dominant_factor = max(temp_score, precip_score, wind_score, code_score)

    risk_score = max(weighted_avg, 0.6 * dominant_factor + 0.4 * weighted_avg)

    return round(min(risk_score, 100), 1)


def risk_level(score: float) -> str:

    if score <= 25:
        return "Faible"
    elif score <= 50:
        return "Modéré"
    elif score <= 75:
        return "Élevé"
    else:
        return "Critique"

def add_features(df: pd.DataFrame) -> pd.DataFrame:
    df['temperature_category'] = df['temperature_2m_max'].apply(categorize_temp)
    df['precipitation_category'] = df['precipitation_sum'].apply(categorize_precipitation)
    df['wind_category'] = df['wind_gusts_10m_max'].apply(categorize_wind)
    df['weather_category'] = df['weather_code'].apply(categorize_weather_code)

    df['day_of_week'] = df['date'].dt.day_name()
    df['is_weekend'] = df['date'].dt.dayofweek.isin([5, 6])
    df['days_ahead'] = (df['date'] - pd.Timestamp.today().normalize()).dt.days

    before = len(df)
    df = df[df['days_ahead'] >= 0]
    removed = before - len(df)
    if removed > 0:
        logger.warning(f"{removed} lignes avec une date passée (days_ahead < 0) supprimées")

    df['risk_score'] = df.apply(calculate_risk_score, axis=1)
    df['risk_level'] = df['risk_score'].apply(risk_level)

    return df


GOLD_COLUMNS = [
    "city_id", "date",
    "temperature_2m_max", "temperature_2m_min",
    "precipitation_sum", "precipitation_probability_max",
    "wind_speed_10m_max", "wind_gusts_10m_max", "weather_code",
    "temperature_category", "precipitation_category",
    "wind_category", "weather_category",
    "risk_score", "risk_level",
    "day_of_week", "is_weekend", "days_ahead",
]
if __name__ == "__main__":
    df = pd.read_csv("silver/weather_silver.csv", parse_dates=['date'])
    df = add_features(df)

    df_gold = df[GOLD_COLUMNS]

    df_gold.to_csv("gold/weather_gold.csv", index=False)

    logger.info(f"Gold terminé : {len(df_gold)} lignes sauvegardées dans gold/weather_gold.csv")
    print(df_gold['risk_level'].value_counts())
    print(pd.read_csv("gold/weather_gold.csv").columns.tolist())
