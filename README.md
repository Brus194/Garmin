# 🏃 Garmin træningsdashboard

Et personligt dashboard over hele din træning, bygget oven på din Garmin-konto.
Et lokalt script henter data fra Garmin Connect → gemmer det i en lokal
SQLite-database → et Streamlit-dashboard visualiserer det → du eksponerer det via
et link og embedder det i Notion.

```
Garmin Connect  ──>  scripts/run_sync.py  ──>  garmin.db (SQLite)  ──>  Streamlit  ──>  Cloudflare Tunnel  ──>  Notion-embed
   (din konto)        (python-garminconnect)     (lokal historik)        (grafer)         (offentlig URL)
```

## Hvorfor denne tilgang?
- **Officiel Garmin Connect Developer API** (Health/Activity API) er kun til
  erhverv og kræver ansøgning + godkendelse → uegnet til personligt brug.
- **[`python-garminconnect`](https://github.com/cyberjunky/python-garminconnect)**
  logger ind med din egen konto (samme flow som Garmin Connect-app'en), virker
  med det samme og er gratis. Det er det, vi bruger.

## Hvad hentes?
Aktiviteter (løb, cykling, m.m.), daglig sundhed (skridt, kalorier, hvilepuls,
stress, body battery), søvn (faser + score), HRV, training readiness, VO2 max samt
vægt og kropssammensætning.

## Kom i gang

### 1. Installér
```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Konfigurér
```bash
cp .env.example .env
# Redigér .env og udfyld GARMIN_EMAIL + GARMIN_PASSWORD
```

### 3. Hent data (første gang interaktivt pga. MFA)
```bash
python scripts/run_sync.py
```
Indtast MFA-koden hvis du bliver bedt om det. Tokens gemmes i
`~/.garminconnect/`, så efterfølgende kørsler er uovervågede. Første kørsel
backfiller `BACKFILL_DAYS` (default 365) dages historik.

### 4. Start dashboardet
```bash
streamlit run garmin_dashboard/app.py
```
Åbn `http://localhost:8501`.

### 5. Embed i Notion
Følg **[deploy/cloudflared.md](deploy/cloudflared.md)** for at give dashboardet en
offentlig URL via Cloudflare Tunnel og indsætte det som et `/embed` i din
Notion-side (brug `?embed=true` i URL'en for et rent look).

### 6. Daglig opdatering
Følg **[deploy/schedule.md](deploy/schedule.md)** for at køre `run_sync.py`
automatisk hver dag (cron / launchd / Task Scheduler).

## Projektstruktur
```
garmin_dashboard/
  config.py    # indlæser .env, stier og konstanter
  client.py    # Garmin-login med token-genbrug + MFA
  db.py        # SQLite-skema + idempotente upserts
  sync.py      # henter alle datatyper og skriver til DB (inkrementelt)
  app.py       # Streamlit-dashboard (læser kun fra DB)
scripts/run_sync.py   # entrypoint til daglig sync
deploy/               # tunnel- og scheduler-opsætning
```

## Sikkerhed
`.env` og `*.db` er git-ignored, og Garmin-tokens lever kun lokalt i
`~/.garminconnect/`. Intet hemmeligt committes til repoet. Deler du dashboardets
URL offentligt, så husk at den eksponerer dine træningsdata – brug evt. Cloudflare
Access til at låse den med login.
```
