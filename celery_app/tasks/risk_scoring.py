"""
Risk scoring engine.

For each active vessel with an open shipment order:
  1. ETA deviation score   (0–40 pts)
  2. Port congestion score (0–30 pts)
  3. Weather hazard score  (0–30 pts)
  ────────────────────────
  Total 0–100 → LOW / MEDIUM / HIGH

Run via Celery beat every 10 minutes.
"""

import math
import os
from datetime import datetime, timezone

import structlog

from celery_app.app import app
from celery_app.db import execute
from celery_app.tasks.alerts import send_risk_alert

log = structlog.get_logger()

RISK_HIGH = float(os.getenv("RISK_HIGH_THRESHOLD", 70))
RISK_MEDIUM = float(os.getenv("RISK_MEDIUM_THRESHOLD", 40))

# Vessel considered "stationary" below this speed (knots)
STATIONARY_SPEED_KNOTS = 0.5

# Weather thresholds
WAVE_MODERATE_M = 2.5
WAVE_HIGH_M = 4.0
WIND_HIGH_MS = 20.0  # m/s ≈ 39 knots

# ETA scoring caps
ETA_MAX_DELAY_DAYS = 10  # delay beyond this gets max score


def _risk_level(score: float) -> str:
    if score >= RISK_HIGH:
        return "HIGH"
    if score >= RISK_MEDIUM:
        return "MEDIUM"
    return "LOW"


def _eta_score(delay_days: float) -> float:
    if delay_days <= 0:
        return 0.0
    # Logarithmic scale: 1 day → ~13 pts, 5 days → ~32 pts, 10 days → 40 pts
    capped = min(delay_days, ETA_MAX_DELAY_DAYS)
    return round(40.0 * math.log1p(capped) / math.log1p(ETA_MAX_DELAY_DAYS), 2)


def _congestion_score(congestion_pct: float | None) -> float:
    if congestion_pct is None:
        return 0.0
    # Linear: 0% → 0 pts, 100% → 30 pts
    return round(max(0.0, min(30.0, congestion_pct * 0.30)), 2)


def _weather_score(wave_m: float | None, wind_ms: float | None) -> float:
    score = 0.0
    if wave_m is not None:
        if wave_m >= WAVE_HIGH_M:
            score += 30.0
        elif wave_m >= WAVE_MODERATE_M:
            score += 15.0
        else:
            score += max(0, wave_m * 4.0)
    if wind_ms is not None and wind_ms >= WIND_HIGH_MS:
        score = max(score, 20.0)
    return round(min(30.0, score), 2)


def _build_summary(
    vessel_name: str,
    order_ref: str,
    delay_days: float,
    congestion_pct: float | None,
    wave_m: float | None,
    risk_level: str,
) -> str:
    parts = []
    if delay_days > 0:
        parts.append(f"{delay_days:.1f} day{'s' if delay_days != 1 else ''} delayed")
    if congestion_pct and congestion_pct > 50:
        parts.append(f"destination port at {congestion_pct:.0f}% congestion")
    if wave_m and wave_m >= WAVE_MODERATE_M:
        parts.append(f"{wave_m:.1f}m waves in path")
    detail = ", ".join(parts) if parts else "on schedule"
    return f"Vessel {vessel_name} (Order {order_ref}): {detail} → {risk_level} risk"


@app.task(name="celery_app.tasks.risk_scoring.score_vessel", bind=True, max_retries=3)
def score_vessel(self, mmsi: int, order_id: str):
    try:
        _score_vessel(mmsi, order_id)
    except Exception as exc:
        log.exception("score_vessel_failed", mmsi=mmsi, order_id=order_id)
        raise self.retry(exc=exc, countdown=30)


def _score_vessel(mmsi: int, order_id: str):
    now = datetime.now(tz=timezone.utc)

    # ── 1. Get latest vessel position ────────────────────────────────────────
    pos_row = execute(
        """
        SELECT lat, lon, speed, time
        FROM vessel_positions
        WHERE mmsi = :mmsi
        ORDER BY time DESC
        LIMIT 1
        """,
        {"mmsi": mmsi},
    ).fetchone()

    if pos_row is None:
        log.warning("no_position_data", mmsi=mmsi)
        return

    lat, lon, speed, last_seen = pos_row

    # ── 2. Get order details ─────────────────────────────────────────────────
    order_row = execute(
        """
        SELECT o.order_ref, o.scheduled_eta, o.customer,
               v.name AS vessel_name,
               dp.id AS dest_port_id, dp.name AS dest_port_name
        FROM shipment_orders o
        JOIN vessels v ON v.mmsi = o.vessel_mmsi
        JOIN ports dp ON dp.id = o.dest_port
        WHERE o.id = :order_id
        """,
        {"order_id": order_id},
    ).fetchone()

    if order_row is None:
        return

    order_ref, scheduled_eta, customer, vessel_name, dest_port_id, dest_port_name = order_row

    # ── 3. Estimate current ETA via dead reckoning ────────────────────────────
    # Get destination port coordinates
    port_row = execute(
        "SELECT ST_Y(berth_center) AS lat, ST_X(berth_center) AS lon FROM ports WHERE id = :pid",
        {"pid": dest_port_id},
    ).fetchone()

    if port_row and speed and speed > STATIONARY_SPEED_KNOTS:
        dest_lat, dest_lon = port_row
        # Great-circle distance in nautical miles (Haversine)
        R_NM = 3440.065
        phi1, phi2 = math.radians(lat), math.radians(dest_lat)
        dphi = math.radians(dest_lat - lat)
        dlam = math.radians(dest_lon - lon)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
        dist_nm = 2 * R_NM * math.asin(math.sqrt(a))
        hours_remaining = dist_nm / speed if speed > 0 else None
        estimated_eta = (
            now.replace(tzinfo=timezone.utc) +
            __import__("datetime").timedelta(hours=hours_remaining)
        ) if hours_remaining else None
    else:
        estimated_eta = None

    if estimated_eta and scheduled_eta:
        if isinstance(scheduled_eta, str):
            scheduled_eta = datetime.fromisoformat(scheduled_eta)
        delay_days = max(0.0, (estimated_eta - scheduled_eta).total_seconds() / 86400)
    else:
        delay_days = 0.0

    # ── 4. Port congestion at destination ────────────────────────────────────
    congestion_row = execute(
        """
        SELECT congestion_pct
        FROM port_congestion
        WHERE port_id = :pid
        ORDER BY time DESC
        LIMIT 1
        """,
        {"pid": dest_port_id},
    ).fetchone()
    congestion_pct = congestion_row[0] if congestion_row else None

    # ── 5. Weather on projected path (next 48h bounding box) ─────────────────
    weather_row = execute(
        """
        SELECT MAX(wave_height_m), MAX(wind_speed_ms)
        FROM weather_snapshots
        WHERE time > NOW() - INTERVAL '2 hours'
          AND ST_DWithin(
                position::geography,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                500000  -- 500 km radius around current position
              )
        """,
        {"lat": lat, "lon": lon},
    ).fetchone()

    max_wave = weather_row[0] if weather_row else None
    max_wind = weather_row[1] if weather_row else None

    # ── 6. Compute composite score ────────────────────────────────────────────
    e_score = _eta_score(delay_days)
    c_score = _congestion_score(congestion_pct)
    w_score = _weather_score(max_wave, max_wind)
    total = round(e_score + c_score + w_score, 2)
    level = _risk_level(total)
    summary = _build_summary(vessel_name, order_ref, delay_days, congestion_pct, max_wave, level)

    log.info(
        "risk_scored",
        mmsi=mmsi, vessel=vessel_name, order=order_ref,
        total=total, level=level, delay_days=delay_days,
    )

    # ── 7. Persist score ──────────────────────────────────────────────────────
    execute(
        """
        INSERT INTO risk_scores
            (time, mmsi, order_id, total_score, risk_level,
             eta_delay_days, eta_score,
             congestion_pct, congestion_score,
             weather_max_wave_m, weather_score,
             summary)
        VALUES
            (NOW(), :mmsi, :order_id, :total, :level,
             :delay_days, :e_score,
             :congestion_pct, :c_score,
             :max_wave, :w_score,
             :summary)
        """,
        {
            "mmsi": mmsi, "order_id": order_id,
            "total": total, "level": level,
            "delay_days": delay_days, "e_score": e_score,
            "congestion_pct": congestion_pct, "c_score": c_score,
            "max_wave": max_wave, "w_score": w_score,
            "summary": summary,
        },
    )

    # ── 8. Check if alert should fire ────────────────────────────────────────
    _check_and_alert(mmsi, order_id, level, summary, total)


def _check_and_alert(mmsi: int, order_id: str, new_level: str, summary: str, score: float):
    if new_level == "LOW":
        return

    cooldown_h = int(os.getenv("ALERT_COOLDOWN_HOURS", 4))
    row = execute(
        """
        SELECT risk_level, alert_sent, alert_sent_at
        FROM risk_scores
        WHERE mmsi = :mmsi
          AND order_id = :order_id
          AND alert_sent = TRUE
        ORDER BY time DESC
        LIMIT 1
        """,
        {"mmsi": mmsi, "order_id": order_id},
    ).fetchone()

    if row:
        prev_level, _, prev_alert_at = row
        if prev_alert_at:
            hours_since = (datetime.now(tz=timezone.utc) - prev_alert_at).total_seconds() / 3600
            if hours_since < cooldown_h and prev_level == new_level:
                return  # still in cooldown with same level

    # Fire alert async
    send_risk_alert.delay(mmsi, order_id, new_level, summary, score)

    # Mark alert sent on the most recent score row
    execute(
        """
        UPDATE risk_scores SET alert_sent = TRUE, alert_sent_at = NOW()
        WHERE mmsi = :mmsi AND order_id = :order_id
          AND time = (
              SELECT time FROM risk_scores
              WHERE mmsi = :mmsi AND order_id = :order_id
              ORDER BY time DESC LIMIT 1
          )
        """,
        {"mmsi": mmsi, "order_id": order_id},
    )


@app.task(name="celery_app.tasks.risk_scoring.score_all_active_vessels")
def score_all_active_vessels():
    """Dispatch individual scoring tasks for every active in-transit order."""
    rows = execute(
        """
        SELECT o.vessel_mmsi, o.id::text
        FROM shipment_orders o
        WHERE o.status = 'in_transit'
          AND o.vessel_mmsi IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM vessel_positions vp
              WHERE vp.mmsi = o.vessel_mmsi
                AND vp.time > NOW() - INTERVAL '2 hours'
          )
        """
    ).fetchall()

    log.info("dispatching_risk_scores", count=len(rows))
    for mmsi, order_id in rows:
        score_vessel.delay(int(mmsi), order_id)
