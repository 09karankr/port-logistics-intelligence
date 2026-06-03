"""
Port congestion detector.

For each port:
  1. Count vessels that are stationary (speed < 0.5 kn) within the anchorage radius
  2. Compare to rolling 90-day baseline → congestion percentile
  3. Store snapshot in port_congestion table
"""

import math
import structlog

from celery_app.app import app
from celery_app.db import execute

log = structlog.get_logger()

STATIONARY_KNOTS = 0.5
STATIONARY_WINDOW_HOURS = 2  # vessel must have been slow for at least this long


@app.task(name="celery_app.tasks.congestion.compute_all_ports")
def compute_all_ports():
    ports = execute("SELECT id, name, anchorage_radius_nm FROM ports").fetchall()
    for port_id, port_name, radius_nm in ports:
        compute_port_congestion.delay(port_id, port_name, radius_nm or 10.0)


@app.task(name="celery_app.tasks.congestion.compute_port_congestion", bind=True, max_retries=2)
def compute_port_congestion(self, port_id: int, port_name: str, radius_nm: float):
    try:
        _compute(port_id, port_name, radius_nm)
    except Exception as exc:
        log.exception("congestion_compute_failed", port_id=port_id)
        raise self.retry(exc=exc, countdown=60)


def _compute(port_id: int, port_name: str, radius_nm: float):
    radius_m = radius_nm * 1852  # nautical miles → meters

    # Count vessels currently anchored/stationary in anchorage zone
    anchored_row = execute(
        """
        WITH recent AS (
            SELECT DISTINCT ON (mmsi) mmsi, speed, lat, lon, nav_status, time
            FROM vessel_positions
            WHERE time > NOW() - INTERVAL '30 minutes'
            ORDER BY mmsi, time DESC
        )
        SELECT COUNT(*) AS cnt
        FROM recent r
        JOIN ports p ON p.id = :port_id
        WHERE r.speed < :max_speed
          AND ST_DWithin(
                ST_SetSRID(ST_MakePoint(r.lon, r.lat), 4326)::geography,
                p.anchorage_center::geography,
                :radius_m
              )
        """,
        {"port_id": port_id, "max_speed": STATIONARY_KNOTS, "radius_m": radius_m},
    ).fetchone()
    vessels_anchored = anchored_row[0] if anchored_row else 0

    # Count vessels at berth
    berth_row = execute(
        """
        WITH recent AS (
            SELECT DISTINCT ON (mmsi) mmsi, speed, lat, lon, nav_status
            FROM vessel_positions
            WHERE time > NOW() - INTERVAL '30 minutes'
            ORDER BY mmsi, time DESC
        )
        SELECT COUNT(*) AS cnt
        FROM recent r
        JOIN ports p ON p.id = :port_id
        WHERE ST_DWithin(
                ST_SetSRID(ST_MakePoint(r.lon, r.lat), 4326)::geography,
                p.berth_center::geography,
                p.berth_radius_nm * 1852
              )
        """,
        {"port_id": port_id},
    ).fetchone()
    vessels_at_berth = berth_row[0] if berth_row else 0

    # Rolling 90-day average for baseline
    baseline_row = execute(
        """
        SELECT AVG(vessels_anchored)
        FROM port_congestion
        WHERE port_id = :port_id
          AND time > NOW() - INTERVAL '90 days'
        """,
        {"port_id": port_id},
    ).fetchone()
    baseline = float(baseline_row[0]) if baseline_row and baseline_row[0] else None

    if baseline and baseline > 0:
        congestion_pct = min(100.0, (vessels_anchored / baseline) * 100.0)
    elif vessels_anchored > 5:
        # No baseline yet — use raw count heuristic
        congestion_pct = min(100.0, vessels_anchored * 10.0)
    else:
        congestion_pct = 0.0

    execute(
        """
        INSERT INTO port_congestion
            (time, port_id, vessels_anchored, vessels_at_berth, congestion_pct, baseline_anchored)
        VALUES
            (NOW(), :port_id, :anchored, :berth, :pct, :baseline)
        """,
        {
            "port_id": port_id,
            "anchored": vessels_anchored,
            "berth": vessels_at_berth,
            "pct": congestion_pct,
            "baseline": baseline,
        },
    )

    log.info(
        "congestion_computed",
        port=port_name,
        anchored=vessels_anchored,
        berth=vessels_at_berth,
        pct=congestion_pct,
    )
