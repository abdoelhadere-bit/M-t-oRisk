import os
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()


@st.cache_resource
def get_engine():
    url = (
        f"postgresql+psycopg2://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
        f"@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    )
    return create_engine(url)


@st.cache_data
def load_data() -> pd.DataFrame:
    engine = get_engine()
    query = """
        SELECT
            c.city_ascii, c.lat, c.lng, c.population,
            f.date, f.temperature_2m_max, f.temperature_2m_min,
            f.precipitation_sum, f.wind_gusts_10m_max, f.weather_code,
            f.temperature_category, f.precipitation_category,
            f.wind_category, f.weather_category,
            f.risk_score, f.risk_level, f.day_of_week, f.is_weekend, f.days_ahead
        FROM forecasts f
        JOIN cities c ON c.id = f.city_id
        ORDER BY c.city_ascii, f.date
    """
    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn)
    return df