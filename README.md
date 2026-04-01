# Salt River Daily Report

Automated daily email report for the Salt River below Stewart Mountain Dam, Mesa AZ.

Fetches live CFS (flow rate) and gauge height from the USGS Water Data API, stores all historical readings in a SQLite database, and emails a formatted report every morning via GitHub Actions — no server or local computer required.

---

## What the email includes

- Current CFS and gauge height
- Year-over-year CFS comparison chart (configurable years)
- **Float Day: YES / NO** based on your configured minimum CFS
- Alert if the river has changed dramatically since the previous reading
- 7-day reading history table
- All times displayed in MST (Arizona does not observe daylight saving time)

---

## Configuration

Edit [`config.json`](config.json) to change thresholds and chart years:

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
| `gauge_site` | USGS site number | `09502000` (Salt River below Stewart Mtn Dam) |
| `min_cfs` | Minimum CFS to call it a float day | `800` |
| `alert_change_pct` | % change since yesterday that triggers a dramatic-change alert | `25` |
| `chart_years` | Years to plot on the comparison chart | `[2024, 2025, 2026]` |

To add an older year to the chart, append it to `chart_years` — historical data is fetched from USGS automatically on the next Action run.

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

---

## How the database works

`data/river.db` is a SQLite database committed directly to this repository. **GitHub Actions is the sole owner of this file** — it checks out the repo, adds today's reading, and commits the updated DB back automatically.

On the very first run, Actions also backfills full-year daily data from USGS for every year listed in `chart_years`. No manual setup required.

**Never commit `data/river.db` from your local machine.** Doing so causes merge conflicts with Actions' commits. See the contributing workflow below.

---

## Contributing / making code changes

Always add specific files rather than `git add .` to avoid accidentally staging the database:

```bash
git add src/ config.json requirements.txt .github/ .gitattributes README.md
git commit -m "your message"
git pull --rebase origin main
git push
```

If you ever get a `river.db` conflict during rebase, resolve it by keeping the remote version (Actions' copy is authoritative):

```bash
git checkout --theirs data/river.db
git add data/river.db
git rebase --continue
git push
```

One-time local setup (run once per machine after cloning):

```bash
git config pull.rebase true
git config merge.sqlite-ours.name "Keep local SQLite DB on conflict"
git config merge.sqlite-ours.driver true
```

---

## Project structure

```
├── src/
│   ├── fetch.py      # USGS Water Data API client
│   ├── db.py         # SQLite read/write (readings + daily_values tables)
│   ├── alerts.py     # Change detection and threshold logic
│   ├── backfill.py   # Historical data fetch from USGS daily collection
│   ├── chart.py      # Year-over-year matplotlib chart generator
│   ├── report.py     # HTML email builder and Gmail sender
│   └── main.py       # Entry point
├── data/
│   └── river.db      # SQLite database — managed exclusively by Actions
├── .github/
│   └── workflows/
│       └── daily_report.yml
├── .gitattributes    # Marks river.db as binary to prevent merge conflicts
├── config.json       # User-editable thresholds and chart years
└── requirements.txt
```

---

## Data source

[USGS Water Data OGC API](https://api.waterdata.usgs.gov/ogcapi/v0/openapi?f=html) —
Site [09502000](https://waterdata.usgs.gov/monitoring-location/09502000/),
Salt River below Stewart Mountain Dam, AZ.
Data is public domain.
