from fastapi import APIRouter, Depends, Query
import asyncpg

from api.core.db import get_pool

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/port-performance")
async def port_performance(
    days: int = Query(default=90, ge=7, le=365),
    pool: asyncpg.Pool = Depends(get_pool),
):
    """Which ports are consistently congested? Ranked by avg congestion over N days."""
    rows = await pool.fetch(
        """
        SELECT
            p.id AS port_id,
            p.name AS port_name,
            p.country,
            AVG(pcd.avg_congestion_pct)   AS avg_congestion_pct,
            MAX(pcd.peak_congestion_pct)  AS peak_congestion_pct,
            COUNT(*) FILTER (WHERE pcd.avg_congestion_pct > 50) AS days_over_50_pct
        FROM port_congestion_daily pcd
        JOIN ports p ON p.id = pcd.port_id
        WHERE pcd.bucket > NOW() - ($1 || ' days')::INTERVAL
        GROUP BY p.id, p.name, p.country
        ORDER BY avg_congestion_pct DESC NULLS LAST
        """,
        str(days),
    )
    return [dict(r) for r in rows]


@router.get("/lane-risk")
async def lane_risk(
    months: int = Query(default=6, ge=1, le=24),
    pool: asyncpg.Pool = Depends(get_pool),
):
    """Average risk score per shipping lane (origin→dest) by calendar month."""
    rows = await pool.fetch(
        """
        SELECT
            op.name  AS origin,
            dp.name  AS destination,
            EXTRACT(MONTH FROM rs.time)::INT AS month,
            AVG(rs.total_score)             AS avg_risk_score,
            COUNT(*)                        AS shipment_count
        FROM risk_scores rs
        JOIN shipment_orders o ON o.id = rs.order_id
        JOIN ports op ON op.id = o.origin_port
        JOIN ports dp ON dp.id = o.dest_port
        WHERE rs.time > NOW() - ($1 || ' months')::INTERVAL
        GROUP BY op.name, dp.name, month
        ORDER BY avg_risk_score DESC
        """,
        str(months),
    )
    return [dict(r) for r in rows]


@router.get("/high-risk-shipments")
async def high_risk_shipments(
    limit: int = Query(default=20, ge=1, le=100),
    pool: asyncpg.Pool = Depends(get_pool),
):
    """Active shipments currently at HIGH or MEDIUM risk, ordered by score."""
    rows = await pool.fetch(
        """
        WITH latest_risk AS (
            SELECT DISTINCT ON (mmsi)
                mmsi, order_id, risk_level, total_score, summary, time AS scored_at
            FROM risk_scores
            WHERE time > NOW() - INTERVAL '2 hours'
            ORDER BY mmsi, time DESC
        )
        SELECT
            r.mmsi, v.name AS vessel_name, v.flag,
            o.order_ref, o.customer, o.scheduled_eta,
            op.name AS origin_port, dp.name AS dest_port,
            r.risk_level, r.total_score AS risk_score,
            r.summary, r.scored_at
        FROM latest_risk r
        JOIN shipment_orders o ON o.id = r.order_id
        JOIN vessels v ON v.mmsi = r.mmsi
        JOIN ports op ON op.id = o.origin_port
        JOIN ports dp ON dp.id = o.dest_port
        WHERE r.risk_level IN ('HIGH', 'MEDIUM')
          AND o.status = 'in_transit'
        ORDER BY r.total_score DESC
        LIMIT $1
        """,
        limit,
    )
    return [dict(r) for r in rows]


@router.get("/alert-history")
async def alert_history(
    limit: int = Query(default=50, ge=1, le=500),
    pool: asyncpg.Pool = Depends(get_pool),
):
    rows = await pool.fetch(
        """
        SELECT al.id, al.sent_at, al.mmsi, v.name AS vessel_name,
               al.order_id, al.channel, al.risk_level, al.message,
               al.delivered, al.error
        FROM alert_log al
        LEFT JOIN vessels v ON v.mmsi = al.mmsi
        ORDER BY al.sent_at DESC
        LIMIT $1
        """,
        limit,
    )
    return [dict(r) for r in rows]


@router.get("/fleet-summary")
async def fleet_summary(pool: asyncpg.Pool = Depends(get_pool)):
    """High-level dashboard stats."""
    row = await pool.fetchrow(
        """
        SELECT
            (SELECT COUNT(DISTINCT mmsi) FROM vessel_positions
             WHERE time > NOW() - INTERVAL '2 hours'
            ) AS active_vessels,
            (SELECT COUNT(*) FROM shipment_orders WHERE status = 'in_transit') AS orders_in_transit,
            (SELECT COUNT(DISTINCT mmsi) FROM risk_scores rs
             WHERE rs.time > NOW() - INTERVAL '2 hours'
               AND rs.risk_level = 'HIGH') AS high_risk_count,
            (SELECT COUNT(DISTINCT mmsi) FROM risk_scores rs
             WHERE rs.time > NOW() - INTERVAL '2 hours'
               AND rs.risk_level = 'MEDIUM') AS medium_risk_count,
            (SELECT COUNT(*) FROM alert_log WHERE sent_at > NOW() - INTERVAL '24 hours') AS alerts_24h
        """
    )
    return dict(row) if row else {}
