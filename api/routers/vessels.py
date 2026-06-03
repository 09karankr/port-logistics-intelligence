from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
import asyncpg

from api.core.db import get_pool
from api.models.schemas import VesselLive, VesselTrackPoint, RiskScore

router = APIRouter(prefix="/vessels", tags=["vessels"])


@router.get("/live", response_model=list[VesselLive])
async def get_live_vessels(
    pool: asyncpg.Pool = Depends(get_pool),
):
    """All vessels seen in the last 2 hours with their latest position and risk level."""
    rows = await pool.fetch(
        """
        WITH latest AS (
            SELECT DISTINCT ON (mmsi)
                mmsi, lat, lon, speed, heading, nav_status, time
            FROM vessel_positions
            WHERE time > NOW() - INTERVAL '2 hours'
            ORDER BY mmsi, time DESC
        ),
        latest_risk AS (
            SELECT DISTINCT ON (mmsi)
                mmsi, risk_level, total_score
            FROM risk_scores
            WHERE time > NOW() - INTERVAL '1 hour'
            ORDER BY mmsi, time DESC
        )
        SELECT
            l.mmsi, v.name, v.flag, v.vessel_type_name,
            l.lat, l.lon, l.speed, l.heading, l.nav_status,
            l.time AS last_seen,
            r.risk_level, r.total_score AS risk_score
        FROM latest l
        LEFT JOIN vessels v ON v.mmsi = l.mmsi
        LEFT JOIN latest_risk r ON r.mmsi = l.mmsi
        ORDER BY r.total_score DESC NULLS LAST
        """
    )
    return [VesselLive(**dict(r)) for r in rows]


@router.get("/{mmsi}/track", response_model=list[VesselTrackPoint])
async def get_vessel_track(
    mmsi: int,
    hours: int = Query(default=24, ge=1, le=168),
    pool: asyncpg.Pool = Depends(get_pool),
):
    """Historical track for a vessel, sampled to max 500 points."""
    rows = await pool.fetch(
        """
        SELECT time, lat, lon, speed, heading
        FROM vessel_positions
        WHERE mmsi = $1
          AND time > NOW() - ($2 || ' hours')::INTERVAL
        ORDER BY time ASC
        LIMIT 500
        """,
        mmsi, str(hours),
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"No track data for MMSI {mmsi}")
    return [VesselTrackPoint(**dict(r)) for r in rows]


@router.get("/{mmsi}/risk", response_model=RiskScore)
async def get_vessel_risk(
    mmsi: int,
    pool: asyncpg.Pool = Depends(get_pool),
):
    """Latest risk score for a vessel."""
    row = await pool.fetchrow(
        """
        SELECT time, mmsi, order_id, total_score, risk_level,
               eta_delay_days, eta_score, congestion_pct, congestion_score,
               weather_max_wave_m, weather_score, summary
        FROM risk_scores
        WHERE mmsi = $1
        ORDER BY time DESC
        LIMIT 1
        """,
        mmsi,
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"No risk score for MMSI {mmsi}")
    return RiskScore(**dict(row))


@router.get("/{mmsi}/risk/history", response_model=list[RiskScore])
async def get_vessel_risk_history(
    mmsi: int,
    hours: int = Query(default=72, ge=1, le=720),
    pool: asyncpg.Pool = Depends(get_pool),
):
    rows = await pool.fetch(
        """
        SELECT time, mmsi, order_id, total_score, risk_level,
               eta_delay_days, eta_score, congestion_pct, congestion_score,
               weather_max_wave_m, weather_score, summary
        FROM risk_scores
        WHERE mmsi = $1
          AND time > NOW() - ($2 || ' hours')::INTERVAL
        ORDER BY time DESC
        """,
        mmsi, str(hours),
    )
    return [RiskScore(**dict(r)) for r in rows]
