"""Hent data fra Garmin Connect og skriv det til den lokale SQLite-database.

Designet til at være robust: hver dato/metrik hentes i sin egen try/except, så en
enkelt manglende dag eller et endpoint-fejl ikke stopper hele synkroniseringen.
Kør via ``scripts/run_sync.py`` (fx dagligt fra cron).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from . import config, db
from .client import get_client

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Små hjælpere til sikker udtrækning af værdier
# --------------------------------------------------------------------------- #
def _num(value: Any) -> float | None:
    """Konvertér til float, eller None hvis det ikke kan lade sig gøre."""
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _dig(obj: Any, *keys: str) -> Any:
    """Følg en kæde af nøgler ned i indlejrede dicts; returnér None ved miss."""
    for key in keys:
        if isinstance(obj, dict):
            obj = obj.get(key)
        else:
            return None
    return obj


def _date_range(start: date, end: date):
    """Generér alle datoer fra start til og med end."""
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _determine_start(conn) -> date:
    """Find startdato for synkronisering ud fra hvad der allerede er i basen."""
    last = db.last_synced_date(conn, "daily_health")
    if last:
        last_date = datetime.fromisoformat(last).date()
        return last_date - timedelta(days=config.SYNC_OVERLAP_DAYS)
    return date.today() - timedelta(days=config.BACKFILL_DAYS)


# --------------------------------------------------------------------------- #
# Per-datatype synkronisering
# --------------------------------------------------------------------------- #
def sync_activities(conn, client, start: date, end: date) -> int:
    """Hent alle aktiviteter i datointervallet."""
    activities = client.get_activities_by_date(start.isoformat(), end.isoformat())
    rows = []
    for act in activities or []:
        start_local = act.get("startTimeLocal", "")
        rows.append(
            {
                "activity_id": act.get("activityId"),
                "date": start_local[:10] if start_local else None,
                "type": _dig(act, "activityType", "typeKey"),
                "name": act.get("activityName"),
                "distance_m": _num(act.get("distance")),
                "duration_s": _num(act.get("duration")),
                "avg_speed_mps": _num(act.get("averageSpeed")),
                "calories": _num(act.get("calories")),
                "avg_hr": _num(act.get("averageHR")),
                "max_hr": _num(act.get("maxHR")),
                "elevation_gain_m": _num(act.get("elevationGain")),
                "training_effect": _num(act.get("aerobicTrainingEffect")),
                "anaerobic_effect": _num(act.get("anaerobicTrainingEffect")),
            }
        )
    return db.upsert_many(conn, "activities", rows)


def sync_daily_health(conn, client, day: date) -> None:
    """Daglige sundhedstal: skridt, kalorier, puls, stress, body battery."""
    iso = day.isoformat()
    stats = client.get_stats(iso) or {}
    row = {
        "date": iso,
        "steps": stats.get("totalSteps"),
        "calories_total": _num(stats.get("totalKilocalories")),
        "calories_active": _num(stats.get("activeKilocalories")),
        "intensity_minutes_moderate": stats.get("moderateIntensityMinutes"),
        "intensity_minutes_vigorous": stats.get("vigorousIntensityMinutes"),
        "resting_hr": _num(stats.get("restingHeartRate")),
        "max_hr": _num(stats.get("maxHeartRate")),
        "min_hr": _num(stats.get("minHeartRate")),
        "stress_avg": _num(stats.get("averageStressLevel")),
        "body_battery_high": _num(stats.get("bodyBatteryHighestValue")),
        "body_battery_low": _num(stats.get("bodyBatteryLowestValue")),
    }
    db.upsert(conn, "daily_health", row)


def sync_sleep(conn, client, day: date) -> None:
    """Søvn: total varighed, faser og score."""
    iso = day.isoformat()
    data = client.get_sleep_data(iso) or {}
    dto = data.get("dailySleepDTO") or {}
    if not dto.get("sleepTimeSeconds"):
        return  # ingen registreret søvn denne nat
    row = {
        "date": iso,
        "total_sleep_s": _num(dto.get("sleepTimeSeconds")),
        "deep_s": _num(dto.get("deepSleepSeconds")),
        "light_s": _num(dto.get("lightSleepSeconds")),
        "rem_s": _num(dto.get("remSleepSeconds")),
        "awake_s": _num(dto.get("awakeSleepSeconds")),
        "score": _num(_dig(dto, "sleepScores", "overall", "value")),
    }
    db.upsert(conn, "sleep", row)


def sync_hrv(conn, client, day: date) -> None:
    """Heart Rate Variability (natlig gns. + status)."""
    iso = day.isoformat()
    data = client.get_hrv_data(iso) or {}
    summary = data.get("hrvSummary") or {}
    if not summary:
        return
    row = {
        "date": iso,
        "last_night_avg": _num(summary.get("lastNightAvg")),
        "weekly_avg": _num(summary.get("weeklyAvg")),
        "status": summary.get("status"),
    }
    db.upsert(conn, "hrv", row)


def sync_training(conn, client, day: date) -> None:
    """Training readiness + VO2 max (løb/cykling)."""
    iso = day.isoformat()
    row: dict[str, Any] = {"date": iso}

    try:
        readiness = client.get_training_readiness(iso)
        if isinstance(readiness, list) and readiness:
            readiness = readiness[0]
        if isinstance(readiness, dict):
            row["readiness_score"] = _num(readiness.get("score"))
            row["readiness_level"] = readiness.get("level")
    except Exception as exc:  # noqa: BLE001
        log.debug("training readiness fejlede for %s: %s", iso, exc)

    try:
        metrics = client.get_max_metrics(iso)
        if isinstance(metrics, list) and metrics:
            metrics = metrics[0]
        row["vo2max_running"] = _num(_dig(metrics, "generic", "vo2MaxValue"))
        row["vo2max_cycling"] = _num(_dig(metrics, "cycling", "vo2MaxValue"))
    except Exception as exc:  # noqa: BLE001
        log.debug("max metrics fejlede for %s: %s", iso, exc)

    # Skriv kun hvis vi rent faktisk fik noget ud over datoen.
    if len(row) > 1:
        db.upsert(conn, "training", row)


def sync_body(conn, client, start: date, end: date) -> int:
    """Vægt og kropssammensætning i datointervallet."""
    data = client.get_body_composition(start.isoformat(), end.isoformat()) or {}
    entries = data.get("dateWeightList") or []
    rows = []
    for entry in entries:
        ts = entry.get("date")
        day = (
            datetime.fromtimestamp(ts / 1000).date().isoformat()
            if isinstance(ts, (int, float))
            else None
        )
        weight_g = _num(entry.get("weight"))
        muscle_g = _num(entry.get("muscleMass"))
        rows.append(
            {
                "date": day,
                "weight_kg": weight_g / 1000 if weight_g else None,
                "body_fat_pct": _num(entry.get("bodyFat")),
                "muscle_mass_kg": muscle_g / 1000 if muscle_g else None,
                "bmi": _num(entry.get("bmi")),
            }
        )
    rows = [r for r in rows if r["date"]]
    return db.upsert_many(conn, "body", rows)


# --------------------------------------------------------------------------- #
# Orkestrering
# --------------------------------------------------------------------------- #
def sync_all(start: date | None = None, end: date | None = None) -> None:
    """Synkronisér alle datatyper for det givne interval (default: inkrementelt)."""
    conn = db.connect()
    db.init_db(conn)
    client = get_client()

    end = end or date.today()
    start = start or _determine_start(conn)
    log.info("Synkroniserer %s → %s", start, end)

    # Intervalbaserede endpoints (ét kald).
    try:
        n = sync_activities(conn, client, start, end)
        log.info("Aktiviteter: %d rækker", n)
    except Exception as exc:  # noqa: BLE001
        log.warning("Aktiviteter fejlede: %s", exc)

    try:
        n = sync_body(conn, client, start, end)
        log.info("Krop/vægt: %d rækker", n)
    except Exception as exc:  # noqa: BLE001
        log.warning("Krop/vægt fejlede: %s", exc)

    # Per-dag endpoints.
    per_day = {
        "daglig sundhed": sync_daily_health,
        "søvn": sync_sleep,
        "hrv": sync_hrv,
        "træning": sync_training,
    }
    for day in _date_range(start, end):
        for label, fn in per_day.items():
            try:
                fn(conn, client, day)
            except Exception as exc:  # noqa: BLE001
                log.debug("%s fejlede for %s: %s", label, day, exc)

    conn.close()
    log.info("Synkronisering færdig.")
