# MétéoRisk — Anticiper les perturbations logistiques au Maroc

Pipeline de données qui récupère les prévisions météo des principales villes
marocaines et calcule un score de risque météorologique pour aider une
entreprise de livraison à anticiper les perturbations logistiques (fortes
précipitations, vents, températures extrêmes).

## Contexte métier

Une entreprise de livraison opérant dans plusieurs villes marocaines veut
anticiper les perturbations liées à la météo sur les prochains jours, afin
d'adapter l'organisation de ses livraisons (villes concernées, périodes à
risque). Le projet reste **générique** quant au type de véhicule (le brief
ne précisant pas s'il s'agit de livraison inter-villes ou urbaine) : les
seuils météo retenus s'appuient sur des repères de vigilance météo
standards, applicables à tout usager de la route.

## Sources de données

| Source | Rôle | Lien |
|---|---|---|
| **SimpleMaps** | Liste des villes marocaines et leurs coordonnées GPS | https://simplemaps.com/data/world-cities |
| **Open-Meteo** | API de prévisions météo quotidiennes (gratuite, sans clé) | https://open-meteo.com/en/docs |

### Variables météo récupérées (API Open-Meteo, paramètre `daily`)

| Variable | Description | Usage |
|---|---|---|
| `temperature_2m_max` / `temperature_2m_min` | Températures max/min du jour (°C) | Détection de chaleur/froid extrêmes |
| `precipitation_sum` | Cumul de précipitations du jour (mm) | Risque de pluie forte |
| `precipitation_probability_max` | Probabilité max de précipitation (%) | Fiabilité de la prévision de pluie |
| `wind_speed_10m_max` | Vitesse de vent "de fond" max (km/h) | Récupérée mais non utilisée dans le score |
| `wind_gusts_10m_max` | Rafales de vent max, pics ponctuels (km/h) | Utilisée pour le risque vent (voir note) |
| `weather_code` | Code météo standardisé WMO | Détection de dangers non captés par les seuils numériques (brouillard, orage) |

**Pourquoi les rafales plutôt que la vitesse moyenne pour le vent :** un
pic soudain (rafale) déstabilise davantage un véhicule qu'un vent constant
modéré ; les rafales sont souvent 2 à 3 fois plus fortes que la vitesse
moyenne et représentent le vrai facteur de danger.

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
   Dashboard Streamlit  <──  Orchestré par Airflow (DAG quotidien, dans Docker Compose)
```

**Pourquoi Bronze → Silver → Gold :** chaque couche est intouchable une
fois écrite (sauf régénération complète), ce qui permet de rejouer les
étapes suivantes sans refaire d'appels API si un bug est corrigé en aval —
utile en pratique, notamment lors des incidents de quota API rencontrés en
développement (voir section Limites).

## Sélection des villes

Le fichier `worldcities.csv` de SimpleMaps contient toutes les localités
marocaines recensées (plusieurs centaines, y compris de très petites
communes), ce qui n'a pas de sens pour un cas d'usage logistique et
consommerait rapidement le quota gratuit de l'API Open-Meteo.

**Filtre appliqué :** villes avec une population **≥ 80 000 habitants**.

**Résultat :** **61 villes** retenues sur le territoire marocain.

## Weather Risk Score

### Principe général

Le score est une **moyenne pondérée hybride**, entre 0 et 100, combinant
un sous-score par variable météo. Chaque sous-score est calculé par
**interpolation linéaire continue** entre un seuil bas (`low`, aucun
risque) et un seuil haut (`high`, risque maximal) :

```python
def linear_score(value, low, high):
    if value <= low:  return 0
    if value >= high: return 100
    return (value - low) / (high - low) * 100
```

Une interpolation continue a été préférée à des paliers fixes : elle évite
l'effet "escalier" (deux valeurs très différentes recevant le même score)
et reflète plus fidèlement la gravité réelle de chaque variable.

### Variables, seuils et justification

| Variable | `low` | `high` | Poids | Justification du seuil |
|---|---|---|---|---|
| Température max | 33°C | 45°C | 15% | En dessous de 33°C : chaleur estivale normale au Maroc. 45°C proche des records absolus. |
| Précipitations | 0mm | 35mm | 35% | 35mm/jour correspond au seuil d'entrée de la catégorie "pluie forte" dans les classifications météo standards ; un seuil plus bas est retenu par rapport aux références "grand public" (souvent 50mm) car le Maroc dispose d'infrastructures de drainage plus limitées, rendant un même cumul plus perturbateur. |
| Vent (rafales) | 30 km/h | 80 km/h | 35% | Seuil bas cohérent avec le début des effets sensibles sur la stabilité d'un véhicule (échelle de Beaufort, force 6) ; seuil haut proche d'un vent violent. |
| Code météo (WMO) | — (table de correspondance) | — | 15% | Capte les dangers non visibles dans les seuils numériques (brouillard, orage, grêle), via une table de sévérité par code (0 = ciel dégagé → 100 = orage avec grêle forte). |

**Pourquoi le poids du `weather_code` reste le plus faible malgré son
rôle important :** cette variable est souvent redondante avec les autres
(un orage s'accompagne généralement déjà de pluie et de vent forts) ; son
rôle est complémentaire (capter des cas particuliers comme le brouillard),
pas de porter le score à lui seul.

### Formule de combinaison

```python
weighted_avg = wind*0.35 + precip*0.35 + temp*0.15 + code*0.15
dominant_factor = max(temp_score, precip_score, wind_score, code_score)
risk_score = max(weighted_avg, 0.6 * dominant_factor + 0.4 * weighted_avg)
```

**Pourquoi cette formule hybride, plutôt qu'une simple moyenne pondérée :**
une moyenne pondérée pure dilue un danger extrême isolé (ex : une rafale de
90 km/h avec aucune pluie ni chaleur) dans un score final trop bas pour
refléter le vrai danger. La formule garantit qu'un facteur dominant à 100
pousse le score final à au moins 60 (soit déjà "Élevé"), même si les
autres variables sont calmes.

### Niveaux de risque

| Score | Niveau |
|---|---|
| 0 – 25 | Faible |
| 26 – 50 | Modéré |
| 51 – 75 | Élevé |
| 76 – 100 | Critique |

## Modèle de données

Voir le diagramme UML complet : [`UML_DIAGRAM.md`](./UML_DIAGRAM.md).

Deux tables normalisées :
- **`cities`** : `id` (clé SimpleMaps, stable), `city_ascii`, `lat`, `lng`, `population`.
- **`forecasts`** : `id` (auto-incrémenté), `city_id` (FK → `cities.id`), `date`,
  les variables météo brutes, les catégories métier, `risk_score`, `risk_level`,
  les features temporelles (`day_of_week`, `is_weekend`, `days_ahead`), et
  `run_date` (horodatage de dernière mise à jour).

### Stratégie anti-doublons

Contrainte `UNIQUE(city_id, date)` sur `forecasts`, combinée à un chargement
en **upsert** (`INSERT ... ON CONFLICT (city_id, date) DO UPDATE`, via
SQLAlchemy). Rejouer le pipeline plusieurs fois pour la même date met à
jour la prévision existante plutôt que de créer un doublon — testé et
confirmé (le nombre de lignes reste stable après plusieurs exécutions
répétées du DAG).

## Analyse SQL

Fichier : [`sql/analysis_queries.sql`](./sql/analysis_queries.sql). Six
requêtes répondant aux questions métier :

1. Villes avec les températures les plus élevées
2. Villes/jours avec les plus fortes précipitations (événements précis)
3. Villes avec le risque moyen le plus élevé
4. Périodes (dates) avec le risque maximal, toutes villes confondues
5. Pour chaque ville, la période la plus risquée (`DISTINCT ON`, syntaxe PostgreSQL)
6. Bonus : nombre de villes couvertes, températures et précipitations max globales

## Dashboard Streamlit

Fichiers : [`dashboard/db.py`](./dashboard/db.py) (connexion + requête,
mises en cache via `@st.cache_resource` / `@st.cache_data`) et
[`dashboard/app.py`](./dashboard/app.py) (filtres et visualisations).

### Filtres
- Ville(s) — sélection multiple
- Période — plage de dates (couvre aussi bien un jour unique qu'un intervalle)
- Niveau de risque — sélection multiple

### Visualisations, une par question métier

| Question métier | Visualisation | Détail |
|---|---|---|
| Villes au risque **moyen** le plus élevé | Carte (couleur/taille = risk_score moyen par ville) | Répond géographiquement, sans graphique séparé |
| Températures les plus élevées | Bar chart horizontal (top 10) | Comparaison directe |
| Précipitations les plus fortes | Scatter plot (date × précipitation, coloré par ville) | Événements précis, pas un agrégat par ville |
| Périodes à risque maximal **+** pire période par ville | Heatmap (villes × dates, couleur = risk_score) | Une colonne répond à la 1ère question, une ligne à la 2nde — fusion de deux questions dans un seul graphique |

*Captures d'écran à insérer ici : `[dashboard-carte.png]`, `[dashboard-graphiques.png]`, `[dashboard-heatmap.png]`.*

## Orchestration Airflow

Fichier : [`dags/meteorisk_dag.py`](./dags/meteorisk_dag.py).

- **5 tâches séquentielles** (`BashOperator`) : `extract_cities >> extract_weather >> clean_silver >> feature_engineering_gold >> load_postgres`.
- **Planification** : `@daily`, `catchup=False` (pas de rattrapage des exécutions passées).
- **Gestion des erreurs** : `retries=2`, `retry_delay=3 minutes` par tâche.
- **Mode Airflow** : `standalone` (webserver + scheduler + triggerer dans un seul conteneur, `LocalExecutor`) — choix volontaire pour rester proportionné à la charge du pipeline (5 tâches séquentielles, 1 fois/jour), plutôt qu'une architecture distribuée (Celery + Redis) inutilement complexe ici.
- Chaque script est appelé avec un `cd` explicite vers la racine du projet avant exécution, pour que les chemins relatifs (`bronze/`, `silver/`, `gold/`) se résolvent identiquement en local et dans le conteneur.

## Conteneurisation Docker Compose

Fichier : [`compose.yaml`](./compose.yaml). Trois services :

| Service | Rôle | Dockerfile |
|---|---|---|
| `postgres` | Base de données (schéma métier `meteorisk` + métadonnées Airflow `airflow`, deux bases distinctes dans le même conteneur) | image officielle `postgres:16` |
| `airflow` | Orchestration du pipeline | [`docker/airflow.Dockerfile`](./docker/airflow.Dockerfile) |
| `streamlit` | Dashboard | [`Dockerfile`](./Dockerfile) (racine) |

**Pourquoi deux `Dockerfile` séparés plutôt qu'un seul :** Airflow 2.9.3
exige `sqlalchemy<2.0`, alors que le dashboard utilise une version plus
récente de SQLAlchemy sans contrainte particulière. Réutiliser un seul
fichier de dépendances pour les deux conteneurs provoquait un conflit de
versions cassant Airflow au démarrage — d'où
[`requirements-airflow.txt`](./requirements-airflow.txt), minimal et
dédié, distinct de [`requirements.txt`](./requirements.txt).

Les tables `cities`/`forecasts` (`load/schema.sql`) et la base de
métadonnées Airflow (`docker/init-airflow-db.sql`) sont créées
automatiquement au premier démarrage du conteneur Postgres, via le
mécanisme `docker-entrypoint-initdb.d/`.

## Installation et exécution

### Prérequis
- Docker et Docker Compose installés
- Un fichier `worldcities.csv` (SimpleMaps) placé dans `data/`

### Étapes

```bash
git clone <url-du-repo>
cd meteorisk

cp .env.example .env
# éditer .env : POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB

docker compose up --build
```

### Accès aux services une fois démarrés

| Service | URL |
|---|---|
| Interface Airflow | http://localhost:8080 |
| Dashboard Streamlit | http://localhost:8501 |
| PostgreSQL | `localhost:5432` (ou `docker exec -it meteorisk_postgres psql -U postgres -d meteorisk`) |

**Créer un utilisateur Airflow** (si aucun compte admin n'existe déjà) :
```bash
docker exec -it meteorisk_airflow airflow users create \
    --username admin --firstname <prenom> --lastname <nom> \
    --role Admin --email admin@meteorisk.local --password <mot_de_passe>
```

**Déclencher le pipeline manuellement** (sans attendre l'exécution
quotidienne automatique) : depuis l'interface Airflow, DAG
`meteorisk_pipeline` → bouton ▶️ (Trigger DAG).

**Consulter les logs Airflow** directement depuis l'explorateur de
fichiers, sans passer par l'interface : dossier `airflow_logs/` à la
racine du projet (monté en bind mount).

## Structure du projet

```
meteorisk/
├── bronze/                       # données brutes (échantillon versionné)
├── silver/                       # données nettoyées (échantillon versionné)
├── gold/                         # données enrichies (échantillon versionné)
├── extraction/
│   ├── extract_cities.py
│   └── extract_weather.py
├── transformation/
│   ├── clean_silver.py
│   └── feature_engineering_gold.py
├── load/
│   ├── load_postgres.py
│   └── schema.sql
├── sql/
│   └── analysis_queries.sql
├── dashboard/
│   ├── db.py
│   └── app.py
├── dags/
│   └── meteorisk_dag.py
├── docker/
│   ├── airflow.Dockerfile
│   └── init-airflow-db.sql
├── airflow_logs/                 # logs Airflow (bind mount, généré au démarrage)
├── compose.yaml
├── Dockerfile                    # image Streamlit
├── requirements.txt              # dépendances locales + dashboard
├── requirements-airflow.txt      # dépendances minimales pour le conteneur Airflow
├── .env.example
├── UML_DIAGRAM.md
└── README.md
```

## Limites connues et pistes d'amélioration

- **Absence d'événements extrêmes sur la période testée** : la fenêtre de
  prévision observée pendant le développement (mi-septembre 2026) était
  météorologiquement calme — peu de précipitations, pas de rafales
  extrêmes. Le score reste néanmoins sensible à toute condition dépassant
  les seuils `high` définis, si elle survenait lors d'une exécution future.
- **Léger écart entre le seuil de score du vent (`high=80`) et le seuil
  de la catégorie textuelle "Danger" (`>=90`)** : les deux mécanismes
  (score numérique continu et catégorie discrète) ont été ajustés à des
  moments différents du développement ; une harmonisation stricte des deux
  seuils serait une amélioration mineure possible.
- **Historique des prévisions** : chaque run Bronze archive ses fichiers
  JSON avec un horodatage (`weather_{city_id}_{date}.json`), permettant en
  théorie de reconstituer un historique des prévisions — non exploité plus
  avant dans le dashboard actuel.
- **Pipeline incrémental** : actuellement, chaque run Bronze/Silver/Gold
  retraite l'ensemble des données disponibles plutôt que seulement les
  nouvelles lignes — suffisant au volume actuel (61 villes × 7 jours), mais
  à revoir si le nombre de villes augmentait significativement.

