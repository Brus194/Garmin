"""Streamlit-dashboard der visualiserer Garmin-data fra den lokale SQLite-base.

Kør::

    streamlit run garmin_dashboard/app.py

Læser kun fra databasen (skriver aldrig) – data hentes af scripts/run_sync.py.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from garmin_dashboard import config, db

st.set_page_config(page_title="Garmin træningsdashboard", page_icon="🏃", layout="wide")


# --------------------------------------------------------------------------- #
# Dataindlæsning
# --------------------------------------------------------------------------- #
@st.cache_data(ttl=600)
def load_table(table: str) -> pd.DataFrame:
    """Indlæs en tabel som DataFrame (tom hvis basen/tabellen mangler)."""
    if not config.DB_PATH.exists():
        return pd.DataFrame()
    conn = db.connect()
    try:
        frame = pd.read_sql_query(f"SELECT * FROM {table}", conn)
    except Exception:  # noqa: BLE001 - tabel findes måske endnu ikke
        frame = pd.DataFrame()
    finally:
        conn.close()
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        frame = frame.sort_values("date")
    return frame


def _latest(frame: pd.DataFrame, column: str):
    """Seneste ikke-tomme værdi i en kolonne."""
    if frame.empty or column not in frame.columns:
        return None
    series = frame.dropna(subset=[column])
    return series.iloc[-1][column] if not series.empty else None


# --------------------------------------------------------------------------- #
# Hjælp ved tom database
# --------------------------------------------------------------------------- #
if not config.DB_PATH.exists():
    st.title("🏃 Garmin træningsdashboard")
    st.warning(
        "Databasen findes endnu ikke. Kør først synkroniseringen:\n\n"
        "```\npython scripts/run_sync.py\n```"
    )
    st.stop()

activities = load_table("activities")
daily = load_table("daily_health")
sleep = load_table("sleep")
hrv = load_table("hrv")
training = load_table("training")
body = load_table("body")

# --------------------------------------------------------------------------- #
# Sidebar: tidsinterval
# --------------------------------------------------------------------------- #
st.sidebar.header("Filtre")
days_back = st.sidebar.slider("Vis seneste antal dage", 7, 730, 90, step=7)
cutoff = pd.Timestamp(date.today() - timedelta(days=days_back))


def _window(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or "date" not in frame.columns:
        return frame
    return frame[frame["date"] >= cutoff]


act_w = _window(activities)
daily_w = _window(daily)
sleep_w = _window(sleep)
hrv_w = _window(hrv)
training_w = _window(training)
body_w = _window(body)

st.title("🏃 Garmin træningsdashboard")
st.caption(f"Viser data for de seneste {days_back} dage.")

# --------------------------------------------------------------------------- #
# KPI-overblik
# --------------------------------------------------------------------------- #
last7 = activities[activities["date"] >= pd.Timestamp(date.today() - timedelta(days=7))] if not activities.empty else activities

c1, c2, c3, c4, c5, c6 = st.columns(6)
dist_km = (last7["distance_m"].sum() / 1000) if not last7.empty else 0
dur_h = (last7["duration_s"].sum() / 3600) if not last7.empty else 0
c1.metric("Distance (7 dage)", f"{dist_km:.1f} km")
c2.metric("Tid (7 dage)", f"{dur_h:.1f} t")
c3.metric("Aktiviteter (7 dage)", f"{len(last7)}")

rhr = _latest(daily, "resting_hr")
c4.metric("Hvilepuls", f"{rhr:.0f}" if rhr else "–")

sleep_h = None
if not sleep.empty and "total_sleep_s" in sleep:
    recent_sleep = sleep[sleep["date"] >= pd.Timestamp(date.today() - timedelta(days=7))]
    if not recent_sleep.empty:
        sleep_h = recent_sleep["total_sleep_s"].mean() / 3600
c5.metric("Søvn (gns. 7 dage)", f"{sleep_h:.1f} t" if sleep_h else "–")

vo2 = _latest(training, "vo2max_running")
c6.metric("VO2 max (løb)", f"{vo2:.0f}" if vo2 else "–")

st.divider()

# --------------------------------------------------------------------------- #
# Faneblade
# --------------------------------------------------------------------------- #
tab_act, tab_rec, tab_sleep, tab_body = st.tabs(
    ["🏅 Aktiviteter", "❤️ Restitution & sundhed", "😴 Søvn", "⚖️ Krop"]
)

with tab_act:
    if act_w.empty:
        st.info("Ingen aktiviteter i perioden.")
    else:
        act_w = act_w.copy()
        act_w["distance_km"] = act_w["distance_m"] / 1000
        act_w["duration_min"] = act_w["duration_s"] / 60
        act_w["week"] = act_w["date"].dt.to_period("W").dt.start_time

        weekly = (
            act_w.groupby(["week", "type"])["distance_km"].sum().reset_index()
        )
        fig = px.bar(
            weekly, x="week", y="distance_km", color="type",
            title="Ugentligt volumen pr. sportsgren", labels={"distance_km": "km", "week": "Uge"},
        )
        st.plotly_chart(fig, use_container_width=True)

        type_counts = act_w["type"].value_counts().reset_index()
        type_counts.columns = ["type", "antal"]
        fig2 = px.pie(type_counts, names="type", values="antal", title="Fordeling af aktivitetstyper")
        st.plotly_chart(fig2, use_container_width=True)

        st.subheader("Aktiviteter")
        show = act_w[
            ["date", "type", "name", "distance_km", "duration_min", "avg_hr", "calories"]
        ].sort_values("date", ascending=False)
        st.dataframe(show, use_container_width=True, hide_index=True)

with tab_rec:
    if not daily_w.empty and daily_w["resting_hr"].notna().any():
        st.plotly_chart(
            px.line(daily_w, x="date", y="resting_hr", title="Hvilepuls", markers=True),
            use_container_width=True,
        )
    if not hrv_w.empty and hrv_w["last_night_avg"].notna().any():
        st.plotly_chart(
            px.line(hrv_w, x="date", y="last_night_avg", title="HRV (natlig gns.)", markers=True),
            use_container_width=True,
        )
    if not training_w.empty and training_w["readiness_score"].notna().any():
        st.plotly_chart(
            px.line(training_w, x="date", y="readiness_score", title="Training readiness", markers=True),
            use_container_width=True,
        )
    if not daily_w.empty and daily_w["stress_avg"].notna().any():
        st.plotly_chart(
            px.line(daily_w, x="date", y="stress_avg", title="Gns. stress", markers=True),
            use_container_width=True,
        )
    if not daily_w.empty and daily_w["steps"].notna().any():
        st.plotly_chart(
            px.bar(daily_w, x="date", y="steps", title="Skridt pr. dag"),
            use_container_width=True,
        )

with tab_sleep:
    if sleep_w.empty:
        st.info("Ingen søvndata i perioden.")
    else:
        phases = sleep_w.copy()
        for col in ["deep_s", "light_s", "rem_s", "awake_s"]:
            if col in phases:
                phases[col] = phases[col] / 3600
        melt = phases.melt(
            id_vars="date",
            value_vars=[c for c in ["deep_s", "light_s", "rem_s", "awake_s"] if c in phases],
            var_name="fase", value_name="timer",
        )
        labels = {"deep_s": "Dyb", "light_s": "Let", "rem_s": "REM", "awake_s": "Vågen"}
        melt["fase"] = melt["fase"].map(labels)
        st.plotly_chart(
            px.bar(melt, x="date", y="timer", color="fase", title="Søvnfaser pr. nat"),
            use_container_width=True,
        )
        if sleep_w["score"].notna().any():
            st.plotly_chart(
                px.line(sleep_w, x="date", y="score", title="Søvnscore", markers=True),
                use_container_width=True,
            )

with tab_body:
    if body_w.empty:
        st.info("Ingen vægt-/kropsdata i perioden.")
    else:
        if body_w["weight_kg"].notna().any():
            st.plotly_chart(
                px.line(body_w, x="date", y="weight_kg", title="Vægt (kg)", markers=True),
                use_container_width=True,
            )
        if body_w["body_fat_pct"].notna().any():
            st.plotly_chart(
                px.line(body_w, x="date", y="body_fat_pct", title="Fedtprocent", markers=True),
                use_container_width=True,
            )
        if body_w["muscle_mass_kg"].notna().any():
            st.plotly_chart(
                px.line(body_w, x="date", y="muscle_mass_kg", title="Muskelmasse (kg)", markers=True),
                use_container_width=True,
            )
