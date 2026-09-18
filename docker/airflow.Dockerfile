FROM apache/airflow:2.9.3

USER root

# System packages needed for network utilities and Postgres build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

USER airflow

COPY requirements-airflow.txt /requirements-airflow.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /requirements-airflow.txt