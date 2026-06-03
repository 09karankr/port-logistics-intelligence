"""
Alert dispatcher — sends email and/or Slack notifications when a vessel
crosses a risk threshold.
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests
import structlog

from celery_app.app import app
from celery_app.db import execute

log = structlog.get_logger()

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
ALERT_FROM = os.getenv("ALERT_FROM_EMAIL", "alerts@portintel.local")
ALERT_TO = os.getenv("ALERT_TO_EMAIL", "")

SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL", "")

RISK_EMOJI = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}


@app.task(name="celery_app.tasks.alerts.send_risk_alert", bind=True, max_retries=3)
def send_risk_alert(self, mmsi: int, order_id: str, risk_level: str, summary: str, score: float):
    delivered = False
    error = None

    try:
        if SLACK_WEBHOOK:
            _send_slack(risk_level, summary, score)
            delivered = True

        if SMTP_HOST and ALERT_TO:
            _send_email(risk_level, summary, score)
            delivered = True

        if not delivered:
            log.warning("no_alert_channels_configured", mmsi=mmsi)

    except Exception as exc:
        error = str(exc)
        log.exception("alert_send_failed", mmsi=mmsi, order_id=order_id)
        raise self.retry(exc=exc, countdown=60)
    finally:
        execute(
            """
            INSERT INTO alert_log (sent_at, mmsi, order_id, channel, risk_level, message, delivered, error)
            VALUES (NOW(), :mmsi, :order_id, :channel, :level, :msg, :ok, :err)
            """,
            {
                "mmsi": mmsi,
                "order_id": order_id,
                "channel": "slack" if SLACK_WEBHOOK else "email",
                "level": risk_level,
                "msg": summary,
                "ok": delivered,
                "err": error,
            },
        )


def _send_slack(risk_level: str, summary: str, score: float):
    emoji = RISK_EMOJI.get(risk_level, "⚪")
    payload = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} Port Intel Alert — {risk_level} Risk",
                },
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*{summary}*"},
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Risk score: *{score:.1f}/100* | Port Intelligence System",
                    }
                ],
            },
        ]
    }
    resp = requests.post(SLACK_WEBHOOK, json=payload, timeout=10)
    resp.raise_for_status()
    log.info("slack_alert_sent", level=risk_level, score=score)


def _send_email(risk_level: str, summary: str, score: float):
    emoji = RISK_EMOJI.get(risk_level, "")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"{emoji} Port Intel — {risk_level} Risk Alert"
    msg["From"] = ALERT_FROM
    msg["To"] = ALERT_TO

    html = f"""
    <html><body>
    <h2 style="color:{'#d32f2f' if risk_level=='HIGH' else '#f57c00'};">
        {emoji} {risk_level} Risk Shipment Alert
    </h2>
    <p>{summary}</p>
    <p><strong>Risk Score:</strong> {score:.1f} / 100</p>
    <hr>
    <small>Real-Time Port & Logistics Intelligence System</small>
    </body></html>
    """
    msg.attach(MIMEText(summary, "plain"))
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(ALERT_FROM, ALERT_TO, msg.as_string())

    log.info("email_alert_sent", to=ALERT_TO, level=risk_level)
