# Salt River Daily Report

Automated daily email report for the Salt River below Stewart Mountain Dam, Mesa AZ.

Fetches live CFS (flow rate) and gauge height from the USGS Water Data API, stores all historical readings in a SQLite database, and emails a formatted report every morning via GitHub Actions — no server or local computer required.

---

## What the email includes

- Current CFS and gauge height
- **Float Day: YES / NO** based on your configured minimum CFS
- Alert if the river has changed dramatically since the previous reading
- 7-day reading history table

---

## Configuration

Edit [`config.json`](config.json) to change thresholds:

```json
{
  "gauge_site": "09502000",
  "min_cfs": 800,
  "alert_change_pct": 25
}
```

| Field | Description | Default |
|---|---|---|
| `gauge_site` | USGS site number | `09502000` (Stewart Mtn Dam) |
| `min_cfs` | Minimum CFS to call it a float day | `800` |
| `alert_change_pct` | % change since yesterday that triggers a dramatic-change alert | `25` |

Email recipients and credentials are stored as **GitHub Secrets** (never in this file).

---

## GitHub Secrets required

Set these under **Settings → Secrets and variables → Actions**:

| Secret | Description |
|---|---|
| `GMAIL_USER` | Full Gmail address used to send reports |
| `GMAIL_APP_PASSWORD` | 16-character Gmail App Password (not your real password) |
| `EMAIL_RECIPIENTS` | Comma-separated recipient addresses: `a@example.com,b@example.com` |

See [Gmail App Passwords](https://support.google.com/accounts/answer/185833) for how to generate one.

---

## Schedule

The report runs daily at **7:00 AM MST** (14:00 UTC) via GitHub Actions.

To trigger a manual test run: **Actions → Daily River Report → Run workflow**.

To adjust the time, edit the `cron` line in [`.github/workflows/daily_report.yml`](.github/workflows/daily_report.yml):

```yaml
- cron: "0 14 * * *"   # 14:00 UTC = 7:00 AM MST
```

During daylight saving time (MDT, UTC-6), change `14` to `13` for 7:00 AM MDT.

---

## Project structure

```
├── src/
│   ├── fetch.py      # USGS Water Data API client
│   ├── db.py         # SQLite read/write
│   ├── alerts.py     # Change detection and threshold logic
│   ├── report.py     # HTML email builder and Gmail sender
│   └── main.py       # Entry point
├── data/
│   └── river.db      # SQLite database (auto-committed by Actions)
├── .github/
│   └── workflows/
│       └── daily_report.yml
├── config.json       # User-editable thresholds
└── requirements.txt
```

---

## Running locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export GMAIL_USER="you@gmail.com"
export GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"
export EMAIL_RECIPIENTS="you@gmail.com,friend@gmail.com"

python src/main.py
```

---

## Data source

[USGS Water Data OGC API](https://api.waterdata.usgs.gov/ogcapi/v0/openapi?f=html) —
Site [09502000](https://waterdata.usgs.gov/monitoring-location/09502000/),
Salt River below Stewart Mountain Dam, AZ.
Data is public domain.
