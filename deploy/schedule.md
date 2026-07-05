# Automatisering: daglig datasync + hold dashboardet kørende

Tokens gemmes efter første login i `~/.garminconnect/`, så de planlagte kørsler
er uovervågede (ingen MFA-prompt). Kør én gang manuelt først:

```bash
python scripts/run_sync.py   # første gang: indtast MFA-kode
```

Brug den fulde sti til din virtualenv-python i alle eksempler nedenfor
(fx `/home/dig/Garmin/.venv/bin/python`).

---

## Linux / macOS – cron
Redigér med `crontab -e` og tilføj (kl. 06:00 dagligt):
```cron
0 6 * * * cd /sti/til/Garmin && /sti/til/Garmin/.venv/bin/python scripts/run_sync.py >> sync.log 2>&1
```

## macOS – launchd (anbefalet på Mac)
Opret `~/Library/LaunchAgents/com.garmin.dashboard.sync.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.garmin.dashboard.sync</string>
  <key>ProgramArguments</key>
  <array>
    <string>/sti/til/Garmin/.venv/bin/python</string>
    <string>/sti/til/Garmin/scripts/run_sync.py</string>
  </array>
  <key>WorkingDirectory</key><string>/sti/til/Garmin</string>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>6</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key><string>/sti/til/Garmin/sync.log</string>
  <key>StandardErrorPath</key><string>/sti/til/Garmin/sync.log</string>
</dict></plist>
```
Indlæs den: `launchctl load ~/Library/LaunchAgents/com.garmin.dashboard.sync.plist`

## Windows – Task Scheduler
```powershell
schtasks /Create /TN "GarminSync" /TR "C:\sti\Garmin\.venv\Scripts\python.exe C:\sti\Garmin\scripts\run_sync.py" /SC DAILY /ST 06:00
```

---

## Hold dashboard + tunnel kørende
Streamlit og cloudflared skal køre konstant for at Notion-embeddet er live.
Nemmest er at starte dem i hver sin terminal/baggrund:
```bash
streamlit run garmin_dashboard/app.py &
cloudflared tunnel run --url http://localhost:8501 garmin-dashboard &
```
På en altid-tændt maskine kan du gøre dem til services (systemd på Linux,
launchd på Mac) på samme måde som sync-jobbet ovenfor.
