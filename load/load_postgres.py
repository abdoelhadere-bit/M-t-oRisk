import os
import pandas as pd
from sqlalchemy import create_engine, MetaData, Table, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from dotenv import load_dotenv

load_dotenv()


def get_engine():
    url = (
        f"postgresql+psycopg2://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
        f"@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    )
    return create_engine(url)


def upsert_cities(engine, metadata, cities_df: pd.DataFrame):
    cities_table = Table("cities", metadata, autoload_with=engine)
    records = cities_df[["id", "city_ascii", "lat", "lng", "population"]].to_dict(orient="records")

    stmt = pg_insert(cities_table).values(records)
    update_cols = {c.name: stmt.excluded[c.name] for c in cities_table.columns if c.name != "id"}
    stmt = stmt.on_conflict_do_update(index_elements=["id"], set_=update_cols)

    with engine.begin() as conn:
        conn.execute(stmt)
    print(f"{len(records)} villes upsertées")


def upsert_forecasts(engine, metadata, forecasts_df: pd.DataFrame):
    forecasts_table = Table("forecasts", metadata, autoload_with=engine)

    cols = [c.name for c in forecasts_table.columns if c.name not in ("id", "run_date")]
    records = forecasts_df[cols].to_dict(orient="records")

    stmt = pg_insert(forecasts_table).values(records)
    update_cols = {c: stmt.excluded[c] for c in cols if c not in ("city_id", "date")}
    update_cols["run_date"] = func.now()
    stmt = stmt.on_conflict_do_update(index_elements=["city_id", "date"], set_=update_cols)

    with engine.begin() as conn:
        conn.execute(stmt)
    print(f"{len(records)} prévisions upsertées")


def main():
    cities_df = pd.read_csv("bronze/cities_raw.csv")
    gold_df = pd.read_csv("gold/weather_gold.csv", parse_dates=["date"])

    engine = get_engine()
    metadata = MetaData()

    upsert_cities(engine, metadata, cities_df)
    upsert_forecasts(engine, metadata, gold_df)


if __name__ == "__main__":
    main()