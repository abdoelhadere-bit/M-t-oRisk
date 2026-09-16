import pandas as pd
from pathlib import Path

POPULATION_THRESHOLD = 80000

def load_moroccan_cities(csv_path: str) -> pd.DataFrame:

    df = pd.read_csv(csv_path)
    df = df[df['country'] == 'Morocco']

    #Drop useless colums
    df = df.drop(columns=['city', 'iso2', 'iso3', 'capital'])

    # Returns all occurrences of duplicate
    duplicate_rows = df[df.duplicated(keep=False)]

    df = df.drop_duplicates(subset='city_ascii')
    print(df.columns)

    df = df[df['population'] > POPULATION_THRESHOLD]

    # print(duplicate_rows)
    df.to_csv("bronze/cities_raw.csv", index=False)
    return df

if __name__ == "__main__":
    file_path = "bronze/worldcities.csv"
    if Path(file_path).exists():
        df = load_moroccan_cities(file_path)
        print(df.head())

