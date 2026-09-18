from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

# Chemin de base a l'interieur du conteneur Airflow
BASE_DIR = "/opt/airflow"

default_args = {
    "owner": "Abderrahmane",
    "retries": 2,
    "retry_delay": timedelta(minutes=3),
}

with DAG(
    dag_id="meteorisk_pipeline",
    description="Pipeline MeteoRisk : extraction, transformation, feature engineering, chargement PostgreSQL",
    default_args=default_args,
    schedule="@daily",         
    start_date=datetime(2026, 9, 1),
    catchup=False,               
    tags=["meteorisk"],
) as dag:
    

    extract_cities = BashOperator(
        task_id="extract_cities",
        bash_command=f"cd {BASE_DIR} && python extraction/extract_cities.py",
    )

    extract_weather = BashOperator(
        task_id="extract_weather",
        bash_command=f"cd {BASE_DIR} && python extraction/extract_weather.py",
    )

    clean_silver = BashOperator(
        task_id="clean_silver",
        bash_command=f"cd {BASE_DIR} && python transformation/clean_silver.py",
    )

    feature_engineering_gold = BashOperator(
        task_id="feature_engineering_gold",
        bash_command=f"cd {BASE_DIR} && python transformation/feature_engineering_gold.py",
    )

    load_postgres = BashOperator(
        task_id="load_postgres",
        bash_command=f"cd {BASE_DIR} && python load/load_postgres.py",
    )

    # Enchainement sequentiel : chaque etape depend du succes de la precedente
    extract_cities >> extract_weather >> clean_silver >> feature_engineering_gold >> load_postgres