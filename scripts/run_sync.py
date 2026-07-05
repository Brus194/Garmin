#!/usr/bin/env python3
"""Entrypoint til den daglige Garmin-synkronisering.

Kør manuelt::

    python scripts/run_sync.py

Eller via cron/launchd/Task Scheduler (se deploy/schedule.md). Første kørsel
beder om en MFA-kode; derefter genbruges gemte tokens og kørslen er uovervåget.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Gør pakken importérbar når scriptet køres direkte.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from garmin_dashboard.sync import sync_all  # noqa: E402


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        sync_all()
    except Exception:  # noqa: BLE001
        logging.exception("Synkronisering fejlede")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
