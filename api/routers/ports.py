from fastapi import APIRouter, Depends, HTTPException, Query
import asyncpg

from api.core.db import get_pool
from api.models.schemas import PortCongestion, PortPerformance

router = APIRouter(prefix="/ports", tags=["ports"])


@router.get("", response_model=list[dict])
async def list_ports(pool: asyncpg.Pool = Depends(get_pool)):
    rows = await pool.fetch(
        """
        SELECT id, name, country, un_locode,
               ST_Y(berth_center) AS lat, ST_X(berth_center) AS lon
        FROM ports
        ORDER BY name
        """
    )
    return [dict(r) for r in rows]


@router.get("/{port_id}/congestion", response_model=PortCongestion)
async def get_port_congestion(
    port_id: int,
    pool: asyncpg.Pool = Depends(get_pool),
):
    """Live congestion snapshot for a port."""
    row = await pool.fetchrow(
        """
        SELECT pc.port_id, p.name AS port_name, pc.time,
               pc.vessels_anchored, pc.vessels_at_berth, pc.congestion_pct
        FROM port_congestion pc
        JOIN ports p ON p.id = pc.port_id
        WHERE pc.port_id = $1
        ORDER BY pc.time DESC
        LIMIT 1
        """,
        port_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="No congestion data for this port")
    return PortCongestion(**dict(row))


@router.get("/{port_id}/congestion/history")
async def get_port_congestion_history(
    port_id: int,
    days: int = Query(default=30, ge=1, le=365),
    pool: asyncpg.Pool = Depends(get_pool),
):
    rows = await pool.fetch(
        """
        SELECT bucket, port_id, avg_congestion_pct, peak_congestion_pct, avg_vessels_anchored
        FROM port_congestion_daily
        WHERE port_id = $1
          AND bucket > NOW() - ($2 || ' days')::INTERVAL
        ORDER BY bucket ASC
        """,
        port_id, str(days),
    )
    return [dict(r) for r in rows]


@router.get("/congestion/all", response_model=list[dict])
async def get_all_ports_congestion(pool: asyncpg.Pool = Depends(get_pool)):
    """Latest congestion snapshot for every port — for map heatmap."""
    rows = await pool.fetch(
        """
        WITH latest AS (
            SELECT DISTINCT ON (port_id)
                port_id, time, vessels_anchored, vessels_at_berth, congestion_pct
            FROM port_congestion
            ORDER BY port_id, time DESC
        )
        SELECT p.id, p.name, p.country, p.un_locode,
               ST_Y(p.berth_center) AS lat, ST_X(p.berth_center) AS lon,
               l.congestion_pct, l.vessels_anchored, l.time AS last_updated
        FROM ports p
        LEFT JOIN latest l ON l.port_id = p.id
        ORDER BY l.congestion_pct DESC NULLS LAST
        """
    )
    return [dict(r) for r in rows]
