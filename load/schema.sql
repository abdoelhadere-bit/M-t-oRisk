CREATE TABLE cities (
    id INTEGER PRIMARY KEY,
    city_ascii VARCHAR(100) NOT NULL,
    lat DECIMAL(9,6) NOT NULL,
    lng DECIMAL(9,6) NOT NULL,
    population INTEGER
);

CREATE TABLE forecasts (
    id SERIAL PRIMARY KEY,
    city_id INTEGER NOT NULL REFERENCES cities(id),
    date DATE NOT NULL,
    temperature_2m_max DECIMAL(4,1),
    temperature_2m_min DECIMAL(4,1),
    precipitation_sum DECIMAL(5,1),
    precipitation_probability_max SMALLINT,
    wind_speed_10m_max DECIMAL(5,1),
    wind_gusts_10m_max DECIMAL(5,1),
    weather_code SMALLINT,
    temperature_category VARCHAR(30),
    precipitation_category VARCHAR(30),
    wind_category VARCHAR(30),
    weather_category VARCHAR(30),
    risk_score DECIMAL(4,1) NOT NULL,
    risk_level VARCHAR(20) NOT NULL,
    day_of_week VARCHAR(15),
    is_weekend BOOLEAN,
    days_ahead SMALLINT,
    run_date TIMESTAMP NOT NULL DEFAULT NOW(),

    UNIQUE (city_id, date)
);