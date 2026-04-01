"""
Build the HTML email body and send it via Gmail SMTP.
Credentials are read from environment variables GMAIL_USER and GMAIL_APP_PASSWORD.
"""

import os
import smtplib
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


def _float_verdict(cfs: float | None, min_cfs: int) -> tuple[str, str]:
    """Returns (label, hex_color)."""
    if cfs is None:
        return "UNKNOWN", "#757575"
    return ("YES ✓", "#2e7d32") if cfs >= min_cfs else ("NO ✗", "#c62828")


def _alert_blocks(alerts: list[dict]) -> str:
    if not alerts:
        return ""
    styles = {
        "alert":   ("#fff3e0", "#e65100", "⚠️"),
        "warning": ("#fce4ec", "#c62828", "🚨"),
        "info":    ("#e8f5e9", "#388e3c", "ℹ️"),
    }
    blocks = []
    for a in alerts:
        bg, border, icon = styles.get(a["level"], styles["info"])
        blocks.append(
            f'<div style="background:{bg};border-left:4px solid {border};'
            f'padding:12px 16px;margin:8px 0;border-radius:4px;font-size:14px;">'
            f'{icon}&nbsp; {a["message"]}</div>'
        )
    return "\n".join(blocks)


def _history_rows(history: list[dict]) -> str:
    rows = []
    for r in history[:8]:
        cfs_val = f"{r['cfs']:.0f}" if r.get("cfs") is not None else "N/A"
        ht_val  = f"{r['height_ft']:.2f}" if r.get("height_ft") is not None else "N/A"
        ts_val  = _fmt_ts(r.get("fetched_at", ""), "%m/%d/%Y %I:%M %p MST")
        rows.append(
            f'<tr>'
            f'<td style="padding:7px 12px;border-bottom:1px solid #e0e0e0;">{ts_val}</td>'
            f'<td style="padding:7px 12px;border-bottom:1px solid #e0e0e0;text-align:right;">{cfs_val}</td>'
            f'<td style="padding:7px 12px;border-bottom:1px solid #e0e0e0;text-align:right;">{ht_val}</td>'
            f'</tr>'
        )
    return "\n".join(rows) if rows else (
        '<tr><td colspan="3" style="padding:12px;color:#999;text-align:center;">No history yet</td></tr>'
    )


def _change_summary(current_cfs: float | None, history: list[dict]) -> str:
    """One-liner showing change vs previous reading."""
    if current_cfs is None or len(history) < 2:
        return ""
    # history[0] is today's just-inserted reading; history[1] is the previous
    prev_cfs = history[1].get("cfs") if len(history) > 1 else None
    if prev_cfs is None or prev_cfs == 0:
        return ""
    delta = current_cfs - prev_cfs
    pct   = (delta / prev_cfs) * 100
    arrow = "▲" if delta > 0 else "▼"
    color = "#c62828" if delta > 0 else "#1565c0"
    return (
        f'<span style="color:{color};font-weight:bold;">'
        f'{arrow} {abs(delta):.0f} CFS ({abs(pct):.1f}%) vs previous reading'
        f'</span>'
    )


# ── public API ────────────────────────────────────────────────────────────────

def build_html_email(
    current: dict,
    history: list[dict],
    alerts: list[dict],
    config: dict,
) -> str:
    cfs      = current.get("cfs")
    height   = current.get("height_ft")
    ts       = current.get("timestamp") or current.get("fetched_at", "")
    min_cfs  = config.get("min_cfs", 600)

    verdict, verdict_color = _float_verdict(cfs, min_cfs)
    cfs_display    = f"{cfs:.0f}" if cfs is not None else "N/A"
    height_display = f"{height:.2f} ft" if height is not None else "N/A"
    reading_time   = _fmt_ts(ts)
    alert_html     = _alert_blocks(alerts)
    change_html    = _change_summary(cfs, history)
    history_html   = _history_rows(history)

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:Arial,Helvetica,sans-serif;max-width:620px;margin:0 auto;padding:24px;color:#333;background:#f9f9f9;">

  <div style="background:#1565c0;padding:20px 24px;border-radius:8px 8px 0 0;">
    <h1 style="color:white;margin:0;font-size:22px;">🏞️ Salt River Daily Report</h1>
    <p style="color:#bbdefb;margin:6px 0 0;font-size:13px;">
      Below Stewart Mountain Dam &bull; {reading_time}
    </p>
  </div>

  <div style="background:white;padding:24px;border:1px solid #e0e0e0;border-top:none;">

    <!-- Current readings -->
    <div style="background:#e3f2fd;border-radius:8px;padding:20px;text-align:center;margin-bottom:20px;">
      <div style="font-size:56px;font-weight:bold;color:#0d47a1;line-height:1;">
        {cfs_display}
        <span style="font-size:24px;font-weight:normal;">CFS</span>
      </div>
      <div style="font-size:18px;color:#546e7a;margin-top:6px;">{height_display} gauge height</div>
      {f'<div style="margin-top:10px;font-size:13px;">{change_html}</div>' if change_html else ''}
    </div>

    <!-- Float day verdict -->
    <div style="border:2px solid {verdict_color};border-radius:8px;padding:16px;text-align:center;margin-bottom:20px;">
      <div style="font-size:15px;color:#555;margin-bottom:4px;">Float Day?</div>
      <div style="font-size:36px;font-weight:bold;color:{verdict_color};">{verdict}</div>
      <div style="font-size:12px;color:#888;margin-top:4px;">Minimum threshold: {min_cfs} CFS</div>
    </div>

    <!-- Alerts -->
    {f'<div style="margin-bottom:20px;">{alert_html}</div>' if alert_html else ''}

    <!-- History table -->
    <h3 style="color:#1565c0;margin:0 0 10px;font-size:15px;">Recent Readings (7 days)</h3>
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
      <thead>
        <tr style="background:#1565c0;color:white;">
          <th style="padding:8px 12px;text-align:left;font-weight:600;">Date / Time (MST)</th>
          <th style="padding:8px 12px;text-align:right;font-weight:600;">CFS</th>
          <th style="padding:8px 12px;text-align:right;font-weight:600;">Height (ft)</th>
        </tr>
      </thead>
      <tbody>
        {history_html}
      </tbody>
    </table>

    <p style="color:#bbb;font-size:11px;margin-top:24px;padding-top:12px;border-top:1px solid #eee;">
      Data source: USGS Water Data API &bull; Site 09502000 &bull; Salt River below Stewart Mountain Dam, AZ<br>
      To change thresholds, edit <code>config.json</code> in your GitHub repository.
    </p>

  </div>

</body>
</html>"""


def send_email(subject: str, html_body: str, config: dict):
    """
    Send via Gmail SMTP SSL.
    Reads GMAIL_USER, GMAIL_APP_PASSWORD, and EMAIL_RECIPIENTS from env vars
    (set as GitHub Secrets — never stored in config.json).
    EMAIL_RECIPIENTS is a comma-separated list: "a@x.com,b@x.com"
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

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = gmail_user
    msg["To"]      = ", ".join(recipients)
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_user, gmail_password)
        server.sendmail(gmail_user, recipients, msg.as_string())
        print(f"  Email sent to: {', '.join(recipients)}")
