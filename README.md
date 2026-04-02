# Salt River Daily Report

Automated daily email report for the Salt River below Stewart Mountain Dam, Mesa AZ.

Fetches live CFS and gauge height from the USGS Water Data API, stores all historical readings in a SQLite database, and sends a formatted HTML email every morning via GitHub Actions — no server or local computer required.

---

## Email preview

### Daily report
![Daily report email](screenshots/email_report.png)

### Year-over-year chart
![Year-over-year CFS chart](screenshots/chart.png)

> Screenshots may not reflect the latest features. Update after the next morning run.

---

## Features

- **Live readings** — CFS and gauge height fetched from USGS every morning
- **Float Day verdict** — YES / NO badge based on your configured CFS minimum
- **Dramatic change alert** — flags when the river rises or drops sharply overnight
- **Hourly weather forecast** — daylight hours only, with emoji icons, temp, rain %, and wind speed
- **Sunrise & sunset times** — exact hour and minute for the dam location
- **Year-over-year chart** — matplotlib line graph comparing full-year CFS across multiple years, with float threshold line
- **7-day history table** — recent readings at a glance
- **All times in MST** — Arizona does not observe daylight saving time
- **Fully automated** — runs on GitHub Actions, no computer needs to be on

---

## Configuration

[`config.json`](config.json) is the only file you need to edit for day-to-day changes:

```json
{
  "gauge_site": "09502000",
  "min_cfs": 800,
  "alert_change_pct": 25,
  "chart_years": [2024, 2025, 2026]
}
```

| Field | Description | Default |
|---|---|---|
| `gauge_site` | USGS monitoring site number | `09502000` |
| `min_cfs` | Minimum CFS to show Float Day as YES | `800` |
| `alert_change_pct` | % change from yesterday that triggers a dramatic-change alert | `25` |
| `chart_years` | Years displayed on the comparison chart | `[2024, 2025, 2026]` |

To add an older year to the chart, append it to `chart_years` and push — historical data is fetched from USGS automatically on the next Action run.

---

## GitHub Secrets

Set these under **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Description |
|---|---|
| `GMAIL_USER` | Full Gmail address used to send reports (e.g. `you@gmail.com`) |
| `GMAIL_APP_PASSWORD` | 16-character Gmail App Password — **not** your regular Gmail password |
| `EMAIL_RECIPIENTS` | Comma-separated recipient list: `you@gmail.com,friend@gmail.com` |

> **Gmail App Password:** Go to [myaccount.google.com](https://myaccount.google.com) → Security → 2-Step Verification must be ON → search "App passwords" → create one named `river-report`. See [Google's guide](https://support.google.com/accounts/answer/185833) for details.

---

## Schedule

Runs daily at **7:00 AM MST** (14:00 UTC). Arizona does not observe DST so this never needs adjusting.

To trigger a manual test run at any time: **Actions tab → Daily River Report → Run workflow**.

To change the time, edit the `cron` line in [`.github/workflows/daily_report.yml`](.github/workflows/daily_report.yml):

```yaml
- cron: "0 14 * * *"   # 14:00 UTC = 7:00 AM MST
```

---

## How the database works

`data/river.db` is a SQLite database stored directly in this repository.

**GitHub Actions is the sole owner of this file.** On each run it:
1. Checks out the repo (including the existing DB)
2. Auto-backfills any years in `chart_years` that are missing data (first run only)
3. Appends today's reading
4. Commits the updated DB back to the repo

This means the historical data grows automatically over time with no manual intervention.

> **Important:** Never commit `data/river.db` from your local machine. See the workflow below.

---

## Making code changes

Always stage specific files rather than `git add .` — this prevents accidentally committing the database:

```bash
git add src/ config.json requirements.txt .github/ .gitattributes README.md
git commit -m "your message"
git pull --rebase origin main
git push
```

If you get a `river.db` conflict during rebase (because Actions ran since your last pull), resolve it by keeping the remote copy:

```bash
git checkout --theirs data/river.db
git add data/river.db
git rebase --continue
git push
```

### One-time local setup (run once after cloning)

```bash
git config pull.rebase true
git config merge.sqlite-ours.name "Keep local SQLite DB on conflict"
git config merge.sqlite-ours.driver true
```

---

## Project structure

```
├── src/
│   ├── main.py        # Entry point — orchestrates fetch, DB, alerts, weather, chart, email
│   ├── fetch.py       # USGS Water Data OGC API client (river CFS + height)
│   ├── db.py          # SQLite read/write (readings + daily_values tables)
│   ├── alerts.py      # Dramatic-change detection and float threshold logic
│   ├── backfill.py    # Auto-fetches historical yearly data from USGS on first run
│   ├── chart.py       # Builds the year-over-year matplotlib PNG chart
│   ├── weather.py     # Open-Meteo hourly forecast + sunrise/sunset (no API key)
│   └── report.py      # HTML email builder and Gmail SMTP sender
├── data/
│   └── river.db       # SQLite DB — managed exclusively by GitHub Actions
├── .github/
│   └── workflows/
│       └── daily_report.yml  # Cron schedule, secrets, DB commit-back step
├── .gitattributes     # Marks river.db as binary to prevent text-merge conflicts
├── config.json        # Thresholds and chart years — the only file you need to edit
├── requirements.txt   # Python dependencies (requests, matplotlib)
└── LICENSE
```

---

## Data sources

**River data** — [USGS Water Data OGC API](https://api.waterdata.usgs.gov/ogcapi/v0/openapi?f=html)
Site [09502000](https://waterdata.usgs.gov/monitoring-location/09502000/) — Salt River below Stewart Mountain Dam, AZ.
Coordinates: 33.5528°N, 111.5765°W. Data is public domain.
The legacy NWIS API (`waterservices.usgs.gov`) is being phased out; this project uses the current replacement.

**Weather data** — [Open-Meteo](https://open-meteo.com/)
Free, no API key required. Hourly forecast using WMO weather codes, with sunrise/sunset times.
Location uses the same coordinates as the USGS gauge station.
