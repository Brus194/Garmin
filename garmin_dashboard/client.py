"""Garmin Connect-klient med token-genbrug.

Bruger ``python-garminconnect``, som logger ind via samme mobile SSO-flow som
den officielle Garmin Connect-app. Første login er interaktivt (MFA-kode), og
OAuth-tokens gemmes i TOKENSTORE og genbruges/fornyes automatisk bagefter.
"""

from __future__ import annotations

import logging

from garminconnect import Garmin

from . import config

log = logging.getLogger(__name__)


def _prompt_mfa() -> str:
    """Callback som garminconnect kalder, hvis kontoen kræver MFA."""
    return input("Indtast Garmin MFA-kode: ").strip()


def get_client() -> Garmin:
    """Returnér en indlogget Garmin-klient.

    Forsøger først at genbruge gemte tokens fra ``config.TOKENSTORE``. Hvis det
    fejler (udløbet/ingen tokens), logges ind med email/password fra .env, og
    nye tokens gemmes til næste gang.
    """
    tokenstore = str(config.TOKENSTORE)

    # Forsøg login udelukkende via gemte tokens (uovervåget, ingen prompt).
    try:
        client = Garmin()
        client.login(tokenstore)
        log.info("Loggede ind med gemte Garmin-tokens (%s).", tokenstore)
        return client
    except Exception as exc:  # noqa: BLE001 - vi vil altid falde tilbage til fuldt login
        log.info("Kunne ikke genbruge tokens (%s) – laver fuldt login.", exc)

    if not config.GARMIN_EMAIL or not config.GARMIN_PASSWORD:
        raise RuntimeError(
            "GARMIN_EMAIL/GARMIN_PASSWORD mangler. Kopiér .env.example til .env "
            "og udfyld dine loginoplysninger."
        )

    client = Garmin(
        config.GARMIN_EMAIL,
        config.GARMIN_PASSWORD,
        prompt_mfa=_prompt_mfa,
    )
    client.login()
    # Gem tokens så efterfølgende kørsler er uovervågede.
    client.garth.dump(tokenstore)
    log.info("Fuldt login gennemført – tokens gemt i %s.", tokenstore)
    return client
