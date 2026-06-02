"""Central konfiguration – indlæser .env og eksponerer stier/konstanter."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Projektroden er mappen over denne pakke.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Indlæs .env fra projektroden (gør intet hvis filen ikke findes).
load_dotenv(PROJECT_ROOT / ".env")


def _expand(path: str) -> Path:
    """Udvid ~ og gør stien absolut (relative stier løses fra projektroden)."""
    p = Path(path).expanduser()
    return p if p.is_absolute() else (PROJECT_ROOT / p)


GARMIN_EMAIL: str | None = os.getenv("GARMIN_EMAIL")
GARMIN_PASSWORD: str | None = os.getenv("GARMIN_PASSWORD")

# Mappe hvor garminconnect gemmer/genbruger OAuth-tokens.
TOKENSTORE: Path = _expand(os.getenv("GARMIN_TOKENSTORE", "~/.garminconnect"))

# Lokal SQLite-database.
DB_PATH: Path = _expand(os.getenv("DB_PATH", "garmin.db"))

# Hvor langt tilbage der hentes ved allerførste kørsel.
BACKFILL_DAYS: int = int(os.getenv("BACKFILL_DAYS", "365"))

# Antal dage der altid re-synces oven i nye dage (fanger efter-redigeringer).
SYNC_OVERLAP_DAYS: int = int(os.getenv("SYNC_OVERLAP_DAYS", "3"))
