"""
Build the HTML email body and send it via Gmail SMTP.
Credentials are read from environment variables GMAIL_USER and GMAIL_APP_PASSWORD.
"""

import os
import smtplib
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta


# Arizona does not observe daylight saving time — MST (UTC-7) year-round.
MST = timezone(timedelta(hours=-7), name="MST")


# ── helpers ──────────────────────────────────────────────────────────────────

def _fmt_ts(iso_str: str, fmt: str = "%B %d, %Y at %I:%M %p MST") -> str:
    if not iso_str:
        return "Unknown time"
    try:
        return (
            datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
            .astimezone(MST)
            .strftime(fmt)
        )
    except Exception:
        return iso_str


def _float_verdict(cfs: float | None, min_cfs: int) -> tuple[str, str, str]:
    """Returns (label, badge_bg_color, badge_text_color)."""
    if cfs is None:
        return "UNKNOWN", "#8d8070", "#ffffff"
    return ("YES ✓", "#2d5a1b", "#ffffff") if cfs >= min_cfs else ("NO ✗", "#8b3a1a", "#ffffff")


def _alert_blocks(alerts: list[dict]) -> str:
    if not alerts:
        return ""
    styles = {
        "alert":   ("#fef6e4", "#c47f00", "⚠️"),
        "warning": ("#fdecea", "#8b3a1a", "🚨"),
        "info":    ("#eef4eb", "#2d5a1b", "ℹ️"),
    }
    blocks = []
    for a in alerts:
        bg, border, icon = styles.get(a["level"], styles["info"])
        blocks.append(
            f'<div style="background:{bg};border-left:4px solid {border};'
            f'padding:12px 16px;margin:8px 0;border-radius:4px;font-size:14px;color:#3a2e1e;">'
            f'{icon}&nbsp; {a["message"]}</div>'
        )
    return "\n".join(blocks)


def _history_rows(history: list[dict], gauge_unit: str = "cfs") -> str:
    rows = []
    for i, r in enumerate(history[:8]):
        if gauge_unit == "height_ft":
            primary_val = f"{r['height_ft']:.2f} ft" if r.get("height_ft") is not None else "N/A"
            secondary_val = f"{r['cfs']:.0f}" if r.get("cfs") is not None else "N/A"
        else:
            primary_val   = f"{r['cfs']:.0f}" if r.get("cfs") is not None else "N/A"
            secondary_val = f"{r['height_ft']:.2f}" if r.get("height_ft") is not None else "N/A"

        ts_val  = _fmt_ts(r.get("fetched_at", ""), "%m/%d/%Y %I:%M %p MST")
        row_bg  = "#f5f0e6" if i % 2 == 0 else "#fffcf5"
        rows.append(
            f'<tr style="background:{row_bg};">'
            f'<td style="padding:8px 12px;border-bottom:1px solid #ddd5c0;color:#3a2e1e;">{ts_val}</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #ddd5c0;text-align:right;color:#1a6b9a;font-weight:600;">{primary_val}</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #ddd5c0;text-align:right;color:#3a2e1e;">{secondary_val}</td>'
            f'</tr>'
        )
    return "\n".join(rows) if rows else (
        '<tr><td colspan="3" style="padding:12px;color:#a09070;text-align:center;">No history yet</td></tr>'
    )


def _change_summary(current: dict, history: list[dict], gauge_unit: str = "cfs") -> str:
    """One-liner showing change vs previous reading."""
    field = "cfs" if gauge_unit == "cfs" else "height_ft"
    unit  = "CFS" if gauge_unit == "cfs" else "ft"
    current_val = current.get(field)
    if current_val is None or len(history) < 2:
        return ""
    prev_val = history[1].get(field) if len(history) > 1 else None
    if prev_val is None or prev_val == 0:
        return ""
    delta = current_val - prev_val
    pct   = (delta / prev_val) * 100
    arrow = "▲" if delta > 0 else "▼"
    color = "#8b3a1a" if delta > 0 else "#1a6b9a"
    return (
        f'<span style="color:{color};font-weight:bold;">'
        f'{arrow} {abs(delta):.2f} {unit} ({abs(pct):.1f}%) vs previous reading'
        f'</span>'
    )


# ── public API ────────────────────────────────────────────────────────────────

def _weather_section(weather: dict) -> str:
    if not weather:
        return ""

    rows = ""
    for h in weather["hourly"]:
        rows += (
            f'<tr>'
            f'<td style="padding:7px 10px;border-bottom:1px solid #ddd5c0;color:#3a2e1e;white-space:nowrap;">'
            f'  {h["hour_label"]}</td>'
            f'<td style="padding:7px 10px;border-bottom:1px solid #ddd5c0;font-size:18px;text-align:center;">'
            f'  {h["emoji"]}</td>'
            f'<td style="padding:7px 10px;border-bottom:1px solid #ddd5c0;color:#3a2e1e;">'
            f'  {h["condition"]}</td>'
            f'<td style="padding:7px 10px;border-bottom:1px solid #ddd5c0;text-align:right;'
            f'  color:#1a6b9a;font-weight:600;">{h["temp_f"]}°F</td>'
            f'<td style="padding:7px 10px;border-bottom:1px solid #ddd5c0;text-align:right;color:#3a2e1e;">'
            f'  {h["precip_pct"]}%</td>'
            f'<td style="padding:7px 10px;border-bottom:1px solid #ddd5c0;text-align:right;color:#3a2e1e;">'
            f'  {h["wind_mph"]} mph</td>'
            f'</tr>'
        )

    return f"""
    <div style="margin-bottom:22px;">
      <h3 style="color:#2d5a1b;margin:0 0 6px;font-size:14px;text-transform:uppercase;
                 letter-spacing:1px;font-family:Arial,sans-serif;">Weather — Daylight Hours</h3>
      <p style="margin:0 0 10px;font-size:13px;font-family:Arial,sans-serif;color:#6b5c3e;">
        🌅 Sunrise: <strong>{weather["sunrise"]}</strong>
        &nbsp;&nbsp;·&nbsp;&nbsp;
        🌇 Sunset: <strong>{weather["sunset"]}</strong>
      </p>
      <table style="width:100%;border-collapse:collapse;font-size:13px;font-family:Arial,sans-serif;">
        <thead>
          <tr style="background:#2d5a1b;color:#ffffff;">
            <th style="padding:8px 10px;text-align:left;font-weight:600;">Hour</th>
            <th style="padding:8px 10px;text-align:center;font-weight:600;"></th>
            <th style="padding:8px 10px;text-align:left;font-weight:600;">Conditions</th>
            <th style="padding:8px 10px;text-align:right;font-weight:600;">Temp</th>
            <th style="padding:8px 10px;text-align:right;font-weight:600;">Rain</th>
            <th style="padding:8px 10px;text-align:right;font-weight:600;">Wind</th>
          </tr>
        </thead>
        <tbody>
          {rows}
        </tbody>
      </table>
    </div>
    <hr style="border:none;border-top:1px solid #d4c9b0;margin:0 0 18px;">
"""


def _float_day_section(cfs: float | None, min_cfs: int) -> str:
    verdict, badge_bg, badge_fg = _float_verdict(cfs, min_cfs)
    return f"""
    <!-- Float day badge -->
    <div style="text-align:center;margin-bottom:24px;">
      <div style="font-size:13px;color:#6b5c3e;margin-bottom:8px;font-family:Arial,sans-serif;text-transform:uppercase;letter-spacing:1px;">
        Float Day?
      </div>
      <span style="display:inline-block;background:{badge_bg};color:{badge_fg};font-size:26px;font-weight:bold;
                   padding:10px 36px;border-radius:40px;font-family:Arial,sans-serif;letter-spacing:1px;">
        {verdict}
      </span>
      <div style="font-size:12px;color:#9a8060;margin-top:8px;font-family:Arial,sans-serif;">
        Minimum threshold: {min_cfs} CFS
      </div>
    </div>
"""


def build_html_email(
    current: dict,
    history: list[dict],
    alerts: list[dict],
    config: dict,
    chart_png: bytes | None = None,
    weather: dict | None = None,
) -> str:
    cfs        = current.get("cfs")
    height     = current.get("height_ft")
    ts         = current.get("timestamp") or current.get("fetched_at", "")
    min_cfs    = config.get("min_cfs")          # None = no float day badge
    gauge_unit = config.get("gauge_unit", "cfs")
    site_id    = config.get("gauge_site", "")
    report_name    = config.get("report_name", "River Daily Report")
    report_subtitle = config.get("report_subtitle", "")

    reading_time = _fmt_ts(ts)
    alert_html   = _alert_blocks(alerts)
    change_html  = _change_summary(current, history, gauge_unit)

    # Primary hero metric display
    if gauge_unit == "height_ft":
        hero_value   = f"{height:.2f}" if height is not None else "N/A"
        hero_unit    = "ft"
        hero_color   = "#1a6b9a"
        hero_sub     = f"{cfs:.0f} CFS" if cfs is not None else ""
        hero_sub_label = "discharge"
        col1_header  = "Height (ft)"
        col2_header  = "CFS"
    else:
        hero_value   = f"{cfs:.0f}" if cfs is not None else "N/A"
        hero_unit    = "CFS"
        hero_color   = "#1a6b9a"
        hero_sub     = f"{height:.2f} ft" if height is not None else ""
        hero_sub_label = "gauge height"
        col1_header  = "CFS"
        col2_header  = "Height (ft)"

    history_html = _history_rows(history, gauge_unit)
    float_section = _float_day_section(cfs, min_cfs) if min_cfs is not None else ""

    footer_site = f"Site {site_id} &bull; {report_subtitle}" if site_id else report_subtitle

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:Georgia,'Times New Roman',serif;max-width:620px;margin:0 auto;padding:20px;background:#ede8dc;">

  <!-- Header -->
  <div style="background:#2d5a1b;padding:22px 28px;border-radius:8px 8px 0 0;">
    <h1 style="color:#ffffff;margin:0;font-size:22px;letter-spacing:0.5px;">🏞️ {report_name}</h1>
    <p style="color:#c8e6c9;margin:5px 0 0;font-size:13px;font-family:Arial,sans-serif;">
      {report_subtitle} &bull; {reading_time}
    </p>
  </div>

  <!-- Body card -->
  <div style="background:#fffcf5;padding:28px;border:1px solid #d4c9b0;border-top:none;border-radius:0 0 8px 8px;">

    <!-- Hero metric panel -->
    <div style="background:#e8f4f8;border:1px solid #b0d4e8;border-radius:8px;padding:22px;text-align:center;margin-bottom:22px;">
      <div style="font-size:64px;font-weight:bold;color:{hero_color};line-height:1;font-family:Arial,sans-serif;">
        {hero_value}
        <span style="font-size:26px;font-weight:normal;color:#4a8aaa;">{hero_unit}</span>
      </div>
      {f'<div style="font-size:17px;color:#4a6a7a;margin-top:8px;font-family:Arial,sans-serif;">{hero_sub} {hero_sub_label}</div>' if hero_sub else ''}
      {f'<div style="margin-top:10px;font-size:13px;font-family:Arial,sans-serif;">{change_html}</div>' if change_html else ''}
    </div>

    {float_section}

    <!-- Alerts -->
    {f'<div style="margin-bottom:22px;">{alert_html}</div>' if alert_html else ''}

    <!-- Divider -->
    <hr style="border:none;border-top:1px solid #d4c9b0;margin:0 0 18px;">

    <!-- Weather -->
    {_weather_section(weather)}

    <!-- Year-over-year chart (attached as CID to bypass email client restrictions) -->
    {'''<div style="margin-bottom:22px;">
      <h3 style="color:#2d5a1b;margin:0 0 10px;font-size:14px;text-transform:uppercase;
                 letter-spacing:1px;font-family:Arial,sans-serif;">Year over Year</h3>
      <img src="cid:river_chart"
           alt="Year-over-year chart"
           style="width:100%;max-width:580px;border-radius:6px;border:1px solid #d4c9b0;">
    </div>
    <hr style="border:none;border-top:1px solid #d4c9b0;margin:0 0 18px;">''' if chart_png else ''}

    <!-- History table -->
    <h3 style="color:#2d5a1b;margin:0 0 10px;font-size:14px;text-transform:uppercase;
               letter-spacing:1px;font-family:Arial,sans-serif;">
      Recent Readings — 7 Days
    </h3>
    <table style="width:100%;border-collapse:collapse;font-size:13px;font-family:Arial,sans-serif;">
      <thead>
        <tr style="background:#2d5a1b;color:#ffffff;">
          <th style="padding:9px 12px;text-align:left;font-weight:600;border-radius:4px 0 0 0;">Date / Time (MST)</th>
          <th style="padding:9px 12px;text-align:right;font-weight:600;">{col1_header}</th>
          <th style="padding:9px 12px;text-align:right;font-weight:600;border-radius:0 4px 0 0;">{col2_header}</th>
        </tr>
      </thead>
      <tbody>
        {history_html}
      </tbody>
    </table>

    <p style="color:#b0a080;font-size:11px;margin-top:24px;padding-top:12px;
              border-top:1px solid #d4c9b0;font-family:Arial,sans-serif;">
      Data: USGS Water Data API &bull; {footer_site}<br>
      To change settings, edit the config file in your GitHub repository.
    </p>

  </div>

</body>
</html>"""


def send_email(subject: str, html_body: str, config: dict, chart_png: bytes | None = None):
    """
    Send via Gmail SMTP SSL.
    Reads GMAIL_USER, GMAIL_APP_PASSWORD, and EMAIL_RECIPIENTS from env vars
    (set as GitHub Secrets — never stored in config.json).
    EMAIL_RECIPIENTS is a comma-separated list: "a@x.com,b@x.com"

    If chart_png bytes are provided the image is attached as a MIME inline
    attachment (Content-ID: river_chart) so all email clients render it.
    """
    gmail_user     = os.environ.get("GMAIL_USER", "").strip()
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
    raw_recipients = os.environ.get("EMAIL_RECIPIENTS", "").strip()
    recipients     = [r.strip() for r in raw_recipients.split(",") if r.strip()]

    if not gmail_user or not gmail_password:
        raise EnvironmentError(
            "GMAIL_USER and GMAIL_APP_PASSWORD must be set as environment variables."
        )
    if not recipients:
        raise ValueError("EMAIL_RECIPIENTS env var is not set or empty.")

    # multipart/related lets the HTML body reference the attached image by CID
    msg = MIMEMultipart("related")
    msg["Subject"] = subject
    msg["From"]    = gmail_user
    msg["To"]      = ", ".join(recipients)

    msg.attach(MIMEText(html_body, "html", "utf-8"))

    if chart_png:
        img = MIMEImage(chart_png, _subtype="png")
        img.add_header("Content-ID", "<river_chart>")
        img.add_header("Content-Disposition", "inline", filename="river_chart.png")
        msg.attach(img)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_user, gmail_password)
        server.sendmail(gmail_user, recipients, msg.as_string())
        print(f"  Email sent to: {', '.join(recipients)}")
