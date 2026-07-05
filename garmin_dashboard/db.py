"""Lokalt SQLite-lag: skema + idempotente upserts.

Bruger Pythons indbyggede ``sqlite3`` (ingen ekstra afhængigheder). Alle tabeller
har en naturlig primærnøgle (dato eller activity_id), så gentagne synkroniseringer
opdaterer eksisterende rækker i stedet for at duplikere dem.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from . import config

# Tabel -> kolonner. Første kolonne er primærnøglen.
SCHEMA: dict[str, list[str]] = {
    "activities": [
        "activity_id INTEGER PRIMARY KEY",
        "date TEXT",
        "type TEXT",
        "name TEXT",
        "distance_m REAL",
        "duration_s REAL",
        "avg_speed_mps REAL",
        "calories REAL",
        "avg_hr REAL",
        "max_hr REAL",
        "elevation_gain_m REAL",
        "training_effect REAL",
        "anaerobic_effect REAL",
    ],
    "daily_health": [
        "date TEXT PRIMARY KEY",
        "steps INTEGER",
        "calories_total REAL",
        "calories_active REAL",
        "intensity_minutes_moderate INTEGER",
        "intensity_minutes_vigorous INTEGER",
        "resting_hr REAL",
        "max_hr REAL",
        "min_hr REAL",
        "stress_avg REAL",
        "body_battery_high REAL",
        "body_battery_low REAL",
    ],
    "sleep": [
        "date TEXT PRIMARY KEY",
        "total_sleep_s REAL",
        "deep_s REAL",
        "light_s REAL",
        "rem_s REAL",
        "awake_s REAL",
        "score REAL",
    ],
    "hrv": [
        "date TEXT PRIMARY KEY",
        "last_night_avg REAL",
        "weekly_avg REAL",
        "status TEXT",
    ],
    "training": [
        "date TEXT PRIMARY KEY",
        "readiness_score REAL",
        "readiness_level TEXT",
        "training_status TEXT",
        "vo2max_running REAL",
        "vo2max_cycling REAL",
    ],
    "body": [
        "date TEXT PRIMARY KEY",
        "weight_kg REAL",
        "body_fat_pct REAL",
        "muscle_mass_kg REAL",
        "bmi REAL",
    ],
}


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Åbn en forbindelse til databasen (rækker som dict-lignende objekter)."""
    path = Path(db_path) if db_path else config.DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Opret alle tabeller hvis de ikke findes."""
    for table, columns in SCHEMA.items():
        cols = ", ".join(columns)
        conn.execute(f"CREATE TABLE IF NOT EXISTS {table} ({cols})")
    conn.commit()


def _column_names(table: str) -> list[str]:
    """Kolonnenavne (uden type/constraints) for en tabel."""
    names = []
    for col_def in SCHEMA[table]:
        names.append(col_def.split()[0])
    return names


def upsert(conn: sqlite3.Connection, table: str, row: Mapping[str, Any]) -> None:
    """Indsæt eller opdatér én række baseret på primærnøglen."""
    upsert_many(conn, table, [row])


def upsert_many(
    conn: sqlite3.Connection, table: str, rows: Iterable[Mapping[str, Any]]
) -> int:
    """Indsæt/opdatér flere rækker. Kun kendte kolonner medtages. Returnér antal."""
    valid_cols = _column_names(table)
    payload = []
    for row in rows:
        payload.append(tuple(row.get(col) for col in valid_cols))
    if not payload:
        return 0
    placeholders = ", ".join("?" for _ in valid_cols)
    col_list = ", ".join(valid_cols)
    conn.executemany(
        f"INSERT OR REPLACE INTO {table} ({col_list}) VALUES ({placeholders})",
        payload,
    )
    conn.commit()
    return len(payload)


def last_synced_date(conn: sqlite3.Connection, table: str) -> str | None:
    """Seneste dato i en tabel (ISO-streng) eller None hvis tom."""
    column = "date"
    cur = conn.execute(f"SELECT MAX({column}) AS d FROM {table}")
    row = cur.fetchone()
    return row["d"] if row and row["d"] else None
