# Eksponér dashboardet via et link (Cloudflare Tunnel) → embed i Notion

Notion kan kun embedde et **offentligt link**. Streamlit kører lokalt på din
maskine, så vi giver det en stabil offentlig URL med en Cloudflare Tunnel.

## 1. Start dashboardet lokalt
```bash
streamlit run garmin_dashboard/app.py
```
Det lytter nu på `http://localhost:8501`.

## 2. Installér cloudflared
- macOS: `brew install cloudflared`
- Linux: se https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
- Windows: `winget install --id Cloudflare.cloudflared`

## 3a. Hurtig tunnel (nemmest – skiftende URL)
```bash
cloudflared tunnel --url http://localhost:8501
```
Du får en URL som `https://tilfaeldigt-navn.trycloudflare.com`. Den ændrer sig
hver gang du genstarter – fint til at teste, men ikke ideelt til en fast
Notion-embed.

## 3b. Named tunnel (anbefalet – fast URL)
Kræver en gratis Cloudflare-konto + et domæne tilføjet til Cloudflare.
```bash
cloudflared tunnel login
cloudflared tunnel create garmin-dashboard
# Map et fast hostname (skift til dit domæne):
cloudflared tunnel route dns garmin-dashboard garmin.ditdomæne.dk
# Kør tunnelen mod den lokale Streamlit-port:
cloudflared tunnel run --url http://localhost:8501 garmin-dashboard
```
Nu peger `https://garmin.ditdomæne.dk` permanent på dit lokale dashboard.

## 4. Embed i Notion
1. Åbn din Notion-side.
2. Skriv `/embed` og vælg **Embed**.
3. Indsæt linket med embed-parameteren, så Streamlits menu skjules:
   `https://garmin.ditdomæne.dk/?embed=true`
4. Tilpas højden på embed-blokken.

> Dashboardet er kun "live", når både `streamlit` og `cloudflared` kører på din
> maskine. Se `deploy/schedule.md` for at holde dem kørende + daglig datasync.
