MétéoRisk — Anticiper les perturbations logistiques au Maroc

Pipeline de données qui récupère les prévisions météo des principales villes marocaines et calcule un score de risque météorologique pour aider une entreprise de livraison à anticiper les perturbations logistiques (fortes précipitations, vents, températures extrêmes).

Contexte métier

Une entreprise de livraison opérant dans plusieurs villes marocaines veut anticiper les perturbations liées à la météo sur les prochains jours, afin d'adapter l'organisation de ses livraisons (villes concernées, périodes à risque).

Sources de données
Source	Rôle	Lien
SimpleMaps	Liste des villes marocaines et leurs coordonnées GPS	https://simplemaps.com/data/world-cities
Open-Meteo	API de prévisions météo quotidiennes (gratuite, sans clé)	https://open-meteo.com/en/docs
Variables météo récupérées (API Open-Meteo, paramètre daily)
Variable	Description	Usage prévu
temperature_2m_max	Température max du jour (°C)	Détection de vagues de chaleur
temperature_2m_min	Température min du jour (°C)	Détection de froid/gel
precipitation_sum	Cumul de précipitations du jour (mm)	Risque pluie forte / routes glissantes
precipitation_probability_max	Probabilité max de précipitation (%)	Fiabilité de la prévision de pluie
wind_speed_10m_max	Vitesse de vent max (km/h)	Risque pour deux-roues / véhicules légers
wind_gusts_10m_max	Rafales de vent max (km/h)	Risque de pics de vent soudains
weather_code	Code météo standardisé WMO	Détection de conditions dangereuses (orage, brouillard, etc.)

Prévisions récupérées sur 7 jours (aujourd'hui + 6 jours), avec timezone=auto pour aligner les dates sur le fuseau horaire marocain local.

Architecture du pipeline
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
Pourquoi une architecture Bronze → Silver → Gold ?
Bronze : copie brute et intouchable des données sources (CSV filtré + réponses JSON de l'API). Permet de rejouer les étapes suivantes sans refaire d'appels API si un bug est corrigé en aval.
Silver : données nettoyées, typées et jointes (villes + météo), sans encore de logique métier.
Gold : données enrichies avec les catégories métier et le risk_score, prêtes à être chargées en base et consommées par le dashboard.
Sélection des villes

Le fichier worldcities.csv de SimpleMaps contient toutes les localités marocaines recensées (plusieurs centaines, y compris de très petites communes), ce qui n'a pas de sens pour un cas d'usage logistique et consommerait rapidement le quota gratuit de l'API Open-Meteo.

Filtre appliqué : villes avec une population ≥ 100 000 habitants, considérées comme des centres logistiques significatifs pour une entreprise de livraison.

Résultat : 45 villes retenues sur le territoire marocain.

Structure du projet
meteorisk/
├── bronze/                      # données brutes (non versionnées, sauf échantillon)
│   ├── cities_raw.csv
│   └── weather_{id}_{date}.json
├── silver/                      # données nettoyées (à venir)
├── gold/                        # données enrichies (à venir)
├── extraction/
│   ├── extract_cities.py        # filtrage des villes marocaines (SimpleMaps)
│   └── extract_weather.py       # appels API Open-Meteo (bronze)
├── transformation/               # nettoyage Silver (à venir)
├── load/                         # feature engineering, risk score, chargement Postgres (à venir)
├── dashboard/                     # dashboard Streamlit (à venir)
├── dags/                          # DAG Airflow (à venir)
├── sql/                           # schéma + requêtes d'analyse (à venir)
├── docker-compose.yml             # (à venir)
├── requirements.txt
├── .env.example
└── README.md
Installation
Prérequis
Python 3.11+
Un fichier worldcities.csv téléchargé depuis SimpleMaps, placé dans data/
Étapes
bash
git clone <url-du-repo>
cd meteorisk

python3 -m venv venv
source venv/bin/activate        # Windows : venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env            # puis renseigner les identifiants Postgres
Utilisation — Étape 1 : Extraction (Bronze)
1. Filtrer les villes marocaines
bash
python extraction/extract_cities.py

→ Génère bronze/cities_raw.csv (45 villes, population ≥ 100 000 hab.)

2. Récupérer les prévisions météo
bash
python extraction/extract_weather.py

→ Génère un fichier bronze/weather_{id}_{date}.json par ville, contenant la réponse brute de l'API Open-Meteo.

Gestion des erreurs implémentée :

Timeout et erreurs réseau → retry automatique (3 tentatives, backoff progressif)
Quota API journalier dépassé (HTTP 429) → arrêt propre du script avec message explicite
Erreurs HTTP non récupérables (4xx/5xx hors 429) → ville ignorée, traitement des autres villes poursuivi
Délai d'1 seconde entre chaque appel pour ne pas saturer l'API
Réutilisation d'une requests.Session() pour l'ensemble des appels
Roadmap
 Étape 1 — Extraction / Bronze
 Étape 2 — Nettoyage / Silver
 Étape 3 — Feature Engineering / Gold + Weather Risk Score
 Étape 4 — Analyse SQL
 Étape 5 — Dashboard Streamlit
 Étape 6 — Orchestration Airflow + Docker Compose