-- # températures les plus élevées
SELECT
    c.city_ascii,
    MAX(f.temperature_2m_max) AS temp_max_prevue
FROM forecasts f
JOIN cities c ON c.id = f.city_id
GROUP BY c.city_ascii
ORDER BY temp_max_prevue DESC
LIMIT 10;

-- #les plus fortes précipitations
SELECT
    c.city_ascii,
    f.date,
    f.precipitation_sum
FROM forecasts f
JOIN cities c ON c.id = f.city_id
WHERE f.precipitation_sum > 0
ORDER BY f.precipitation_sum DESC
LIMIT 10;

-- #Villes avec le risque moyen le plus élevé
SELECT
    c.city_ascii,
    ROUND(AVG(f.risk_score), 1) AS risk_score_moyen
FROM forecasts f
JOIN cities c ON c.id = f.city_id
GROUP BY c.city_ascii
ORDER BY risk_score_moyen DESC
LIMIT 10;

-- #Périodes avec le risque maximal
SELECT
    f.date,
    f.days_ahead,
    ROUND(AVG(f.risk_score), 1) AS risk_score_moyen_du_jour,
    COUNT(*) FILTER (WHERE f.risk_level IN ('Eleve', 'Critique')) AS nb_villes_a_risque
FROM forecasts f
GROUP BY f.date, f.days_ahead
ORDER BY risk_score_moyen_du_jour DESC;


-- #Pour chaque ville, la période la plus risquée
SELECT DISTINCT ON (city_ascii)
    c.city_ascii,
    f.date,
    f.risk_score,
    f.risk_level
FROM forecasts f
JOIN cities c ON c.id = f.city_id
ORDER BY c.city_ascii, f.risk_score DESC;

SELECT
    COUNT(DISTINCT city_id) AS nombre_villes,
    MAX(temperature_2m_max) AS temp_max_globale,
    MAX(precipitation_sum) AS precipitation_max_globale
FROM forecasts;