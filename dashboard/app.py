import pandas as pd
import plotly.express as px
import streamlit as st

from db import load_data

st.set_page_config(page_title="MétéoRisk", layout="wide")

st.title("MétéoRisk — Anticiper les perturbations logistiques au Maroc")

# ── Chargement des données ──
df = load_data()
df["date"] = pd.to_datetime(df["date"])

# ── Sidebar : filtres ──
st.sidebar.header("Filtres")

villes = sorted(df["city_ascii"].unique())
villes_selectionnees = st.sidebar.multiselect(
    "Ville(s)", options=villes, default=villes
)

date_min, date_max = df["date"].min().date(), df["date"].max().date()
date_debut, date_fin = st.sidebar.date_input(
    "Période (plage de dates)",
    value=(date_min, date_max),
    min_value=date_min,
    max_value=date_max,
)

niveaux = ["Faible", "Modere", "Eleve", "Critique"]
niveaux_selectionnes = st.sidebar.multiselect(
    "Niveau de risque", options=niveaux, default=niveaux
)

# ── Application des filtres ──
mask = (
    df["city_ascii"].isin(villes_selectionnees)
    & (df["date"].dt.date >= date_debut)
    & (df["date"].dt.date <= date_fin)
    & df["risk_level"].isin(niveaux_selectionnes)
)
df_filtered = df[mask]

if df_filtered.empty:
    st.warning("Aucune donnée ne correspond à ces filtres.")
    st.stop()

# ── KPIs ──
col1, col2, col3, col4 = st.columns(4)
col1.metric("Villes sélectionnées", df_filtered["city_ascii"].nunique())
col2.metric("Score de risque moyen", f"{df_filtered['risk_score'].mean():.1f}")
col3.metric("Température max", f"{df_filtered['temperature_2m_max'].max():.1f} °C")
nb_a_risque = df_filtered[df_filtered["risk_level"].isin(["Eleve", "Critique"])][
    "city_ascii"
].nunique()
col4.metric("Villes à risque Élevé/Critique", nb_a_risque)

st.divider()

# ── Carte : risque MOYEN par ville sur la période ──

st.subheader("Carte du risque moyen par ville")

df_map = (
    df_filtered.groupby(["city_ascii", "lat", "lng"], as_index=False)
    .agg(risk_score_moyen=("risk_score", "mean"))
)

fig_map = px.scatter_map(
    df_map,
    lat="lat",
    lon="lng",
    color="risk_score_moyen",
    size="risk_score_moyen",
    hover_name="city_ascii",
    hover_data={"risk_score_moyen": ":.1f", "lat": False, "lng": False},
    color_continuous_scale=["green", "gold", "orange", "red"],
    zoom=4.5,
    height=500,
    map_style="open-street-map",
)
st.plotly_chart(fig_map, use_container_width=True)

st.divider()

# bar chart et scatter des evenements de precipitation
col_a, col_b = st.columns(2)

with col_a:
    st.subheader("Top 10 — Températures max par ville")
    top_temp = (
        df_filtered.groupby("city_ascii")["temperature_2m_max"]
        .max()
        .sort_values(ascending=False)
        .head(10)
        .reset_index()
    )
    fig_temp = px.bar(top_temp, x="temperature_2m_max", y="city_ascii", orientation="h")
    fig_temp.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig_temp, use_container_width=True)

with col_b:
    st.subheader("Précipitations par ville et par jour")
    precip_events = df_filtered[df_filtered["precipitation_sum"] > 0]
    if precip_events.empty:
        st.info("Aucune précipitation enregistrée sur la période/sélection filtrée.")
    else:
        fig_precip = px.scatter(
            precip_events,
            x="date",
            y="precipitation_sum",
            color="city_ascii",
            size="precipitation_sum",
            hover_name="city_ascii",
        )
        fig_precip.update_layout(showlegend=False)
        st.plotly_chart(fig_precip, use_container_width=True)

st.divider()

# heatmap ville x date 
# Une colonne = quel jour est le pire, toutes villes confondues (Q4).
# Une ligne = quel jour est le pire pour cette ville precise (Q5).
st.subheader("Heatmap du risque — période × ville")

pivot = df_filtered.pivot_table(
    index="city_ascii", columns="date", values="risk_score", aggfunc="mean"
)
pivot = pivot.loc[pivot.mean(axis=1).sort_values(ascending=False).index]

fig_heatmap = px.imshow(
    pivot,
    color_continuous_scale=["green", "gold", "orange", "red"],
    labels={"x": "Date", "y": "Ville", "color": "Score de risque"},
    aspect="auto",
)
fig_heatmap.update_layout(height=max(400, 18 * len(pivot)))
st.plotly_chart(fig_heatmap, use_container_width=True)