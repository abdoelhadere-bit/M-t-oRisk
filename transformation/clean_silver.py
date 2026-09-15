import json 
import pandas as pd
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def load_one_weather_file(file_path: Path, city_id: int)-> pd.DataFrame:
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    daily = data['daily']
    df = pd.DataFrame(daily)
    df['city_id'] = city_id
    return df

def load_all_weather(bronze_dir: str)-> pd.DataFrame:
    files = list(bronze_dir.rglob("*.json"))
    logger.info(f"{len(files)} fichiers JSON trouvés dans {bronze_dir}")
    all_dfs = []

    for file in files:
        path_file = Path(file)
        stem = path_file.stem
        parts = stem.split('_')
        city_id = int(parts[1])
        df = load_one_weather_file(file, city_id)
        all_dfs.append(df)
    return pd.concat(all_dfs, ignore_index=True)

def clean_weather(df: pd.DataFrame)-> pd.DataFrame:
    df = df.rename(columns={"time":"date"})
    df['date'] = pd.to_datetime(df['date'])
    # print(df.dtypes)
    df = df.drop_duplicates(subset=["city_id", "date"], keep="last")

    nan_values = df.isna().sum()
    # print(nan_values)

    incoherent = df[df['temperature_2m_min'] > df['temperature_2m_max']]
    if not incoherent.empty:
        logger.warning(f"{len(incoherent)} lignes avec temperature min > temperature max")

    incoherent_2 = df[df['precipitation_sum'] < 0]
    if not incoherent_2.empty:
        logger.warning(f"{len(incoherent_2)} lignes ont une valeur precipitation_sum negative")
    
    incoherent_3 = df[df['wind_speed_10m_max'] < 0]
    if not incoherent_3.empty:
        logger.warning(f"{len(incoherent_3)} lignes ont une valeur wind_speed_10m_max negative")

    df = df.sort_values(['city_id', 'date']).reset_index(drop=True)
    return df

def join_with_cities(weather_df:pd.DataFrame, path_file: str)-> pd.DataFrame:
    df_cities = pd.read_csv(path_file)

    merged = weather_df.merge(df_cities, left_on='city_id', right_on='id', how='left')

    missing = merged[merged['city_ascii'].isna()]
    if not missing.empty:
        logger.warning(f"{len(missing)} lignes n'ont pas de villes")

    return merged
    
if __name__ == "__main__":
    weahter_df = load_all_weather(Path('bronze'))
    clean_df = clean_weather(weahter_df)
    final_df = join_with_cities(clean_df, "bronze/cities_raw.csv")

    final_df.to_csv("silver/weather_silver.csv", index=False)

logger.info(f"Silver termine : {len(final_df)} lignes, {final_df['city_id'].nunique()} villes")