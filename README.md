# MétéoRisk — Anticiper les perturbations logistiques au Maroc

Pipeline de données qui récupère les prévisions météo des principales villes
marocaines et calcule un score de risque météorologique pour aider une
entreprise de livraison à anticiper les perturbations logistiques (fortes
précipitations, vents, températures extrêmes).

## Contexte métier

Une entreprise de livraison opérant dans plusieurs villes marocaines veut
anticiper les perturbations liées à la météo sur les prochains jours, afin
d'adapter l'organisation de ses livraisons (villes concernées, périodes à
risque).

### Scope retenu : livraison urbaine

**Décision :** le projet cible la **livraison urbaine** (deux-roues,
véhicules légers) au sein de chaque ville, et non le transport inter-villes
par poids lourd.

**Pourquoi ça compte :** les seuils météo (vent, chaleur, pluie) ne sont pas
les mêmes selon le type de véhicule. Un scooter est mis en danger par des
rafales de vent bien plus faibles qu'un camion, et le livreur est directement
exposé à la chaleur (pas de cabine climatisée). Ce choix de scope justifie
les seuils utilisés dans les sections suivantes.

## Sources de données

| Source | Rôle | Lien |
|---|---|---|
| **SimpleMaps** | Liste des villes marocaines et leurs coordonnées GPS | https://simplemaps.com/data/world-cities |
| **Open-Meteo** | API de prévisions météo quotidiennes (gratuite, sans clé) | https://open-meteo.com/en/docs |

### Variables météo récupérées (API Open-Meteo, paramètre `daily`)

| Variable | Description | Usage prévu |
|---|---|---|
| `temperature_2m_max` | Température max du jour (°C) | Détection de vagues de chaleur |
| `temperature_2m_min` | Température min du jour (°C) | Détection de froid/gel |
| `precipitation_sum` | Cumul de précipitations du jour (mm) | Risque pluie forte / routes glissantes |
| `precipitation_probability_max` | Probabilité max de précipitation (%) | Fiabilité de la prévision de pluie |
| `wind_speed_10m_max` | Vitesse de vent "de fond" max (km/h) | Récupérée mais non utilisée dans le score (voir note) |
| `wind_gusts_10m_max` | Rafales de vent max, pics ponctuels (km/h) | Risque pour deux-roues / véhicules légers |
| `weather_code` | Code météo standardisé WMO | Détection de conditions dangereuses non captées par les seuils numériques (brouillard, orage, grêle) |

**Note — pourquoi les rafales (`wind_gusts_10m_max`) plutôt que la vitesse
moyenne (`wind_speed_10m_max`) :** un deux-roues n'est pas déstabilisé par un
vent constant modéré, mais par un pic soudain. Les rafales sont souvent 2 à
3 fois plus fortes que la vitesse moyenne et représentent le vrai danger
pour ce type de véhicule.

Prévisions récupérées sur **7 jours** (aujourd'hui + 6 jours), avec
`timezone=auto` pour aligner les dates sur le fuseau horaire marocain local.

## Architecture du pipeline

```
SimpleMaps CSV (villes)  ──┐
                           ├──> BRONZE (données brutes)
Open-Meteo API (météo)  ───┘
        │
        ▼  nettoyage, typage, dédup, jointure
      SILVER (données propres)
        │
        ▼  feature engineering + weather risk score
      GOLD (données enrichies)
        │
        ▼  chargement idempotent (upsert)
    PostgreSQL
        │
        ▼
   Dashboard Streamlit  <──  Orchestré par Airflow (DAG quotidien)
```

### Pourquoi une architecture Bronze → Silver → Gold ?

- **Bronze** : copie brute et intouchable des données sources (CSV filtré +
  réponses JSON de l'API). Permet de rejouer les étapes suivantes sans
  refaire d'appels API si un bug est corrigé en aval.
- **Silver** : données nettoyées, typées et jointes (villes + météo), sans
  encore de logique métier.
- **Gold** : données enrichies avec les catégories métier et le
  `risk_score`, prêtes à être chargées en base et consommées par le
  dashboard.

## Sélection des villes

Le fichier `worldcities.csv` de SimpleMaps contient toutes les localités
marocaines recensées (plusieurs centaines, y compris de très petites
communes), ce qui n'a pas de sens pour un cas d'usage logistique et
consommerait rapidement le quota gratuit de l'API Open-Meteo.

**Filtre appliqué :** villes avec une population **≥ 100 000 habitants**,
considérées comme des centres logistiques significatifs pour une entreprise
de livraison.

**Résultat :** 45 villes retenues sur le territoire marocain.

## Structure du projet

```
meteorisk/
├── bronze/                      # données brutes (non versionnées, sauf échantillon)
│   ├── cities_raw.csv
│   └── weather_{id}_{date}.json
├── silver/                      # données nettoyées (à venir)
├── gold/                        # données enrichies (à venir)
├── extraction/
│   ├── extract_cities.py        # filtrage des villes marocaines (SimpleMaps)
│   └── extract_weather.py       # appels API Open-Meteo (bronze)
├── transformation/
│   └── clean_silver.py          # nettoyage, dédup, jointure villes-météo
├── load/
│   └── feature_engineering_gold.py   # catégories métier + weather risk score (en cours)
│                                  # chargement Postgres (à venir)
├── dashboard/                     # dashboard Streamlit (à venir)
├── dags/                          # DAG Airflow (à venir)
├── sql/                           # schéma + requêtes d'analyse (à venir)
├── docker-compose.yml             # (à venir)
├── requirements.txt
├── .env.example
└── README.md
```

## Installation

### Prérequis
- Python 3.11+
- Un fichier `worldcities.csv` téléchargé depuis SimpleMaps, placé dans `data/`

### Étapes

```bash
git clone <url-du-repo>
cd meteorisk

python3 -m venv venv
source venv/bin/activate        # Windows : venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env            # puis renseigner les identifiants Postgres
```

## Utilisation — Étape 1 : Extraction (Bronze)

### 1. Filtrer les villes marocaines

```bash
python extraction/extract_cities.py
```
→ Génère `bronze/cities_raw.csv` (45 villes, population ≥ 100 000 hab.)

### 2. Récupérer les prévisions météo

```bash
python extraction/extract_weather.py
```
→ Génère un fichier `bronze/weather_{id}_{date}.json` par ville, contenant
la réponse brute de l'API Open-Meteo.

**Gestion des erreurs implémentée :**
- Timeout et erreurs réseau → retry automatique (3 tentatives, backoff progressif)
- Quota API journalier dépassé (HTTP 429) → arrêt propre du script avec message explicite
- Erreurs HTTP non récupérables (4xx/5xx hors 429) → ville ignorée, traitement des autres villes poursuivi
- Délai d'1 seconde entre chaque appel pour ne pas saturer l'API
- Réutilisation d'une `requests.Session()` pour l'ensemble des appels

## Utilisation — Étape 2 : Nettoyage (Silver)

```bash
python transformation/clean_silver.py
```

Cette étape :
1. Charge tous les fichiers JSON de `bronze/weather/` et les transforme
   d'un format "large" (une liste par variable) vers un format "long"
   (une ligne par ville × par jour).
2. Standardise les types (dates en `datetime`, valeurs en numérique).
3. Supprime les doublons sur `(city_id, date)` en gardant la donnée la plus
   récente — utile si le pipeline est relancé plusieurs fois le même jour.
4. Contrôle la cohérence des données (température min > max, précipitations
   ou vent négatifs) et loggue les anomalies détectées.
5. Joint les données météo avec les informations des villes
   (`city_ascii`, `lat`, `lng`, `population`).

→ Génère `silver/weather_silver.csv`.

**Contrôle qualité effectué :** aucune valeur manquante (NaN) ni incohérence
physique détectée sur le jeu de données testé (45 villes × 7 jours).

## Utilisation — Étape 3 : Feature Engineering (Gold, en cours)

```bash
python load/feature_engineering_gold.py
```

### Catégories métier créées

| Colonne | Seuils | Justification |
|---|---|---|
| `temperature_category` | Fraîche (<15°C) / Modérée (15-29°C) / Chaude (30-38°C) / Extrême chaleur (>38°C) | Seuil de 38°C proche des seuils d'alerte canicule adaptés aux régions chaudes |
| `precipitation_category` | Aucune (0mm) / Faible (0-5mm) / Modérée (5-20mm) / Forte (≥20mm) | 20mm/jour cohérent avec les seuils de vigilance "fortes pluies" |
| `wind_category` | Normal (<40 km/h) / Fort (40-70 km/h) / Danger (≥70 km/h) | Basé sur les **rafales**, seuils calibrés pour un deux-roues (voir scope) |
| `weather_category` | Regroupement des codes WMO (Ciel dégagé / Nuageux / Brouillard / Pluie / Neige / Orage) | Source : [doc Open-Meteo](https://open-meteo.com/en/docs), table WMO — capte les dangers non visibles dans les seuils numériques (ex : brouillard) |

### Features temporelles créées

| Colonne | Description | Pourquoi |
|---|---|---|
| `day_of_week` | Nom du jour (Monday, Tuesday...) | Filtrage/lisibilité dans le dashboard |
| `is_weekend` | Booléen samedi/dimanche | L'activité de livraison peut différer le week-end |
| `days_ahead` | Nombre de jours entre la date de la prévision et aujourd'hui (0 = aujourd'hui, 1 = demain...) | Permet de répondre à "quelle **période** est la plus à risque" de façon relative, indépendamment de la date absolue — essentiel car le pipeline tourne quotidiennement et "demain" change de date chaque jour |

**Contrôle qualité :** les lignes avec `days_ahead < 0` (prévisions déjà
passées, dues à un décalage entre la date de récupération Bronze et la date
d'exécution du script) sont filtrées avant chargement en base.

## Roadmap

- [x] Étape 1 — Extraction / Bronze
- [x] Étape 2 — Nettoyage / Silver
- [~] Étape 3 — Feature Engineering / Gold (catégories faites, Weather Risk Score en cours)
- [ ] Étape 4 — Analyse SQL
- [ ] Étape 5 — Dashboard Streamlit
- [ ] Étape 6 — Orchestration Airflow + Docker Compose

## Weather Risk Score

*Section à compléter à l'Étape 3 : méthode de calcul, variables utilisées,
seuils retenus et justification.*

## Modèle de données

*Section à compléter à l'Étape 3 : schéma des tables PostgreSQL (villes,
prévisions, risk_score) et stratégie anti-doublons.*

## Captures d'écran du dashboard

*Section à compléter à l'Étape 5.*

## Auteur

Hamid OUFAKIR — Certification RNCP Développeur.se en intelligence artificielle