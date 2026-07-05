#!/usr/bin/env python3
"""Lille test af dit Garmin-login – kør lokalt for at bekræfte at forbindelsen virker.

Bruger email/password fra din lokale .env (samme login som Garmin Connect-app'en).
Passwordet printes eller gemmes ALDRIG af dette script.

Kør::

    python scripts/test_login.py

Første gang bliver du bedt om en MFA-kode, hvis du har to-faktor slået til.
Herefter genbruges gemte tokens fra ~/.garminconnect/.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

# Gør pakken importérbar når scriptet køres direkte.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from garmin_dashboard import config  # noqa: E402
from garmin_dashboard.client import get_client  # noqa: E402


def _fmt_km(meters) -> str:
    try:
        return f"{float(meters) / 1000:.2f} km"
    except (TypeError, ValueError):
        return "–"


def _fmt_min(seconds) -> str:
    try:
        return f"{float(seconds) / 60:.0f} min"
    except (TypeError, ValueError):
        return "–"


def main() -> int:
    # Tjek at credentials er sat – uden at afsløre dem.
    if not config.GARMIN_EMAIL or not config.GARMIN_PASSWORD:
        print("❌ GARMIN_EMAIL/GARMIN_PASSWORD mangler.")
        print("   Kopiér .env.example til .env og udfyld dit Garmin-login.")
        return 1

    print(f"🔐 Logger ind som {config.GARMIN_EMAIL} …")
    try:
        client = get_client()
    except Exception as exc:  # noqa: BLE001
        print(f"❌ Login fejlede: {exc}")
        print("   Tjek email/password i .env (og MFA-koden hvis du blev spurgt).")
        return 1

    print("✅ Login lykkedes! Tokens er gemt lokalt, så næste gang er automatisk.\n")

    # Vis lidt data som bevis på at adgangen virker.
    try:
        name = client.get_full_name()
        print(f"👤 Konto: {name}")
    except Exception:  # noqa: BLE001
        pass

    today = date.today()
    try:
        stats = client.get_stats(today.isoformat()) or {}
        steps = stats.get("totalSteps")
        rhr = stats.get("restingHeartRate")
        print(f"📊 I dag: {steps if steps is not None else '–'} skridt"
              f" | hvilepuls {rhr if rhr is not None else '–'}")
    except Exception as exc:  # noqa: BLE001
        print(f"(kunne ikke hente dagens tal: {exc})")

    print("\n🏃 Dine seneste aktiviteter:")
    try:
        start = (today - timedelta(days=30)).isoformat()
        activities = client.get_activities_by_date(start, today.isoformat()) or []
        if not activities:
            print("   (ingen aktiviteter i de seneste 30 dage)")
        for act in activities[:3]:
            name = act.get("activityName") or "Uden navn"
            sport = (act.get("activityType") or {}).get("typeKey", "?")
            when = (act.get("startTimeLocal") or "")[:10]
            dist = _fmt_km(act.get("distance"))
            dur = _fmt_min(act.get("duration"))
            print(f"   • {when}  {sport:<12} {name}  –  {dist}, {dur}")
    except Exception as exc:  # noqa: BLE001
        print(f"   (kunne ikke hente aktiviteter: {exc})")

    print("\n🎉 Alt virker – du er klar til at køre den fulde sync:")
    print("   python scripts/run_sync.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
