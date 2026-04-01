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


def _history_rows(history: list[dict]) -> str:
    rows = []
    for i, r in enumerate(history[:8]):
        cfs_val  = f"{r['cfs']:.0f}" if r.get("cfs") is not None else "N/A"
        ht_val   = f"{r['height_ft']:.2f}" if r.get("height_ft") is not None else "N/A"
        ts_val   = _fmt_ts(r.get("fetched_at", ""), "%m/%d/%Y %I:%M %p MST")
        row_bg   = "#f5f0e6" if i % 2 == 0 else "#fffcf5"
        rows.append(
            f'<tr style="background:{row_bg};">'
            f'<td style="padding:8px 12px;border-bottom:1px solid #ddd5c0;color:#3a2e1e;">{ts_val}</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #ddd5c0;text-align:right;color:#1a6b9a;font-weight:600;">{cfs_val}</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #ddd5c0;text-align:right;color:#3a2e1e;">{ht_val}</td>'
            f'</tr>'
        )
    return "\n".join(rows) if rows else (
        '<tr><td colspan="3" style="padding:12px;color:#a09070;text-align:center;">No history yet</td></tr>'
    )


def _change_summary(current_cfs: float | None, history: list[dict]) -> str:
    """One-liner showing change vs previous reading."""
    if current_cfs is None or len(history) < 2:
        return ""
    prev_cfs = history[1].get("cfs") if len(history) > 1 else None
    if prev_cfs is None or prev_cfs == 0:
        return ""
    delta = current_cfs - prev_cfs
    pct   = (delta / prev_cfs) * 100
    arrow = "▲" if delta > 0 else "▼"
    color = "#8b3a1a" if delta > 0 else "#1a6b9a"
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

    verdict, badge_bg, badge_fg = _float_verdict(cfs, min_cfs)
    cfs_display    = f"{cfs:.0f}" if cfs is not None else "N/A"
    height_display = f"{height:.2f} ft" if height is not None else "N/A"
    reading_time   = _fmt_ts(ts)
    alert_html     = _alert_blocks(alerts)
    change_html    = _change_summary(cfs, history)
    history_html   = _history_rows(history)

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:Georgia,'Times New Roman',serif;max-width:620px;margin:0 auto;padding:20px;background:#ede8dc;">

  <!-- Header -->
  <div style="background:#2d5a1b;padding:22px 28px;border-radius:8px 8px 0 0;">
    <h1 style="color:#ffffff;margin:0;font-size:22px;letter-spacing:0.5px;">🏞️ Salt River Daily Report</h1>
    <p style="color:#c8e6c9;margin:5px 0 0;font-size:13px;font-family:Arial,sans-serif;">
      Below Stewart Mountain Dam &bull; {reading_time}
    </p>
  </div>

  <!-- Body card -->
  <div style="background:#fffcf5;padding:28px;border:1px solid #d4c9b0;border-top:none;border-radius:0 0 8px 8px;">

    <!-- CFS + height panel -->
    <div style="background:#e8f4f8;border:1px solid #b0d4e8;border-radius:8px;padding:22px;text-align:center;margin-bottom:22px;">
      <div style="font-size:64px;font-weight:bold;color:#1a6b9a;line-height:1;font-family:Arial,sans-serif;">
        {cfs_display}
        <span style="font-size:26px;font-weight:normal;color:#4a8aaa;">CFS</span>
      </div>
      <div style="font-size:17px;color:#4a6a7a;margin-top:8px;font-family:Arial,sans-serif;">
        {height_display} gauge height
      </div>
      {f'<div style="margin-top:10px;font-size:13px;font-family:Arial,sans-serif;">{change_html}</div>' if change_html else ''}
    </div>

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

    <!-- Alerts -->
    {f'<div style="margin-bottom:22px;">{alert_html}</div>' if alert_html else ''}

    <!-- Divider -->
    <hr style="border:none;border-top:1px solid #d4c9b0;margin:0 0 18px;">

    <!-- History table -->
    <h3 style="color:#2d5a1b;margin:0 0 10px;font-size:14px;text-transform:uppercase;
               letter-spacing:1px;font-family:Arial,sans-serif;">
      Recent Readings — 7 Days
    </h3>
    <table style="width:100%;border-collapse:collapse;font-size:13px;font-family:Arial,sans-serif;">
      <thead>
        <tr style="background:#2d5a1b;color:#ffffff;">
          <th style="padding:9px 12px;text-align:left;font-weight:600;border-radius:4px 0 0 0;">Date / Time (MST)</th>
          <th style="padding:9px 12px;text-align:right;font-weight:600;">CFS</th>
          <th style="padding:9px 12px;text-align:right;font-weight:600;border-radius:0 4px 0 0;">Height (ft)</th>
        </tr>
      </thead>
      <tbody>
        {history_html}
      </tbody>
    </table>

    <p style="color:#b0a080;font-size:11px;margin-top:24px;padding-top:12px;
              border-top:1px solid #d4c9b0;font-family:Arial,sans-serif;">
      Data: USGS Water Data API &bull; Site 09502000 &bull; Salt River below Stewart Mountain Dam, AZ<br>
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
