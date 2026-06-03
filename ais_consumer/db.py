import asyncpg
import structlog
from config import DATABASE_URL

log = structlog.get_logger()

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=2,
            max_size=10,
            command_timeout=30,
        )
        log.info("db_pool_created")
    return _pool


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def upsert_vessel(pool: asyncpg.Pool, vessel: dict):
    await pool.execute(
        """
        INSERT INTO vessels (mmsi, name, imo, call_sign, vessel_type, vessel_type_name, flag, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
        ON CONFLICT (mmsi) DO UPDATE SET
            name            = EXCLUDED.name,
            imo             = EXCLUDED.imo,
            call_sign       = EXCLUDED.call_sign,
            vessel_type     = EXCLUDED.vessel_type,
            vessel_type_name = EXCLUDED.vessel_type_name,
            flag            = EXCLUDED.flag,
            updated_at      = NOW()
        WHERE vessels.name IS DISTINCT FROM EXCLUDED.name
           OR vessels.imo IS DISTINCT FROM EXCLUDED.imo
        """,
        vessel["mmsi"],
        vessel.get("name"),
        vessel.get("imo"),
        vessel.get("call_sign"),
        vessel.get("vessel_type"),
        vessel.get("vessel_type_name"),
        vessel.get("flag"),
    )


async def bulk_insert_positions(pool: asyncpg.Pool, rows: list[dict]):
    if not rows:
        return
    await pool.executemany(
        """
        INSERT INTO vessel_positions
            (time, mmsi, lat, lon, position, speed, heading, course, nav_status, draught, destination, eta_ais)
        VALUES
            ($1, $2, $3, $4, ST_SetSRID(ST_MakePoint($4, $3), 4326),
             $5, $6, $7, $8, $9, $10, $11)
        ON CONFLICT DO NOTHING
        """,
        [
            (
                r["time"], r["mmsi"], r["lat"], r["lon"],
                r.get("speed"), r.get("heading"), r.get("course"),
                r.get("nav_status"), r.get("draught"),
                r.get("destination"), r.get("eta_ais"),
            )
            for r in rows
        ],
    )
