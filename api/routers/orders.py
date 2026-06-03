from fastapi import APIRouter, Depends, HTTPException, Query
import asyncpg

from api.core.db import get_pool
from api.models.schemas import ShipmentOrder, ShipmentOrderCreate

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("", response_model=list[ShipmentOrder])
async def list_orders(
    status: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    pool: asyncpg.Pool = Depends(get_pool),
):
    status_filter = "AND o.status = $2" if status else ""
    params = [limit, status] if status else [limit]

    rows = await pool.fetch(
        f"""
        WITH latest_risk AS (
            SELECT DISTINCT ON (mmsi)
                mmsi, risk_level, total_score
            FROM risk_scores
            ORDER BY mmsi, time DESC
        )
        SELECT
            o.id, o.order_ref, o.customer, o.commodity,
            o.value_usd, o.scheduled_etd, o.scheduled_eta, o.status,
            op.name AS origin_port_name,
            dp.name AS dest_port_name,
            o.vessel_mmsi,
            v.name AS vessel_name,
            r.risk_level AS current_risk_level,
            r.total_score AS current_risk_score
        FROM shipment_orders o
        LEFT JOIN ports op ON op.id = o.origin_port
        LEFT JOIN ports dp ON dp.id = o.dest_port
        LEFT JOIN vessels v ON v.mmsi = o.vessel_mmsi
        LEFT JOIN latest_risk r ON r.mmsi = o.vessel_mmsi
        WHERE 1=1 {status_filter}
        ORDER BY r.total_score DESC NULLS LAST, o.scheduled_eta ASC
        LIMIT $1
        """,
        *params,
    )

    if risk_level:
        rows = [r for r in rows if r["current_risk_level"] == risk_level.upper()]

    return [ShipmentOrder(**dict(r)) for r in rows]


@router.post("", response_model=ShipmentOrder, status_code=201)
async def create_order(
    body: ShipmentOrderCreate,
    pool: asyncpg.Pool = Depends(get_pool),
):
    row = await pool.fetchrow(
        """
        INSERT INTO shipment_orders
            (order_ref, customer, commodity, value_usd,
             origin_port, dest_port, vessel_mmsi,
             scheduled_etd, scheduled_eta, status)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'in_transit')
        RETURNING id, order_ref, customer, commodity, value_usd,
                  scheduled_etd, scheduled_eta, status, vessel_mmsi,
                  origin_port, dest_port
        """,
        body.order_ref, body.customer, body.commodity, body.value_usd,
        body.origin_port_id, body.dest_port_id, body.vessel_mmsi,
        body.scheduled_etd, body.scheduled_eta,
    )
    if row is None:
        raise HTTPException(status_code=500, detail="Failed to create order")

    # Fetch port names for the response
    ports = await pool.fetch(
        "SELECT id, name FROM ports WHERE id = ANY($1)",
        [body.origin_port_id, body.dest_port_id],
    )
    port_map = {r["id"]: r["name"] for r in ports}

    return ShipmentOrder(
        **dict(row),
        origin_port_name=port_map.get(body.origin_port_id),
        dest_port_name=port_map.get(body.dest_port_id),
    )


@router.get("/{order_id}", response_model=ShipmentOrder)
async def get_order(order_id: str, pool: asyncpg.Pool = Depends(get_pool)):
    row = await pool.fetchrow(
        """
        WITH latest_risk AS (
            SELECT DISTINCT ON (mmsi)
                mmsi, risk_level, total_score
            FROM risk_scores
            ORDER BY mmsi, time DESC
        )
        SELECT
            o.id, o.order_ref, o.customer, o.commodity,
            o.value_usd, o.scheduled_etd, o.scheduled_eta, o.status,
            op.name AS origin_port_name,
            dp.name AS dest_port_name,
            o.vessel_mmsi,
            v.name AS vessel_name,
            r.risk_level AS current_risk_level,
            r.total_score AS current_risk_score
        FROM shipment_orders o
        LEFT JOIN ports op ON op.id = o.origin_port
        LEFT JOIN ports dp ON dp.id = o.dest_port
        LEFT JOIN vessels v ON v.mmsi = o.vessel_mmsi
        LEFT JOIN latest_risk r ON r.mmsi = o.vessel_mmsi
        WHERE o.id = $1::uuid
        """,
        order_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return ShipmentOrder(**dict(row))


@router.patch("/{order_id}/status")
async def update_order_status(
    order_id: str,
    status: str = Query(..., pattern="^(pending|in_transit|arrived|delayed|cancelled)$"),
    pool: asyncpg.Pool = Depends(get_pool),
):
    result = await pool.execute(
        "UPDATE shipment_orders SET status = $1, updated_at = NOW() WHERE id = $2::uuid",
        status, order_id,
    )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Order not found")
    return {"ok": True, "status": status}
