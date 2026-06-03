"""
Vessel simulator — procedurally generates ~1,500 vessels across 17 global
shipping lanes to replicate real-world maritime traffic density.
"""

import asyncio
import os
import random
import signal
from datetime import datetime, timezone

import asyncpg
import orjson
import redis.asyncio as aioredis
import structlog
from dotenv import load_dotenv

from engine import build_legs, current_position
from routes import ROUTES, SHIPPING_COMPANIES, VESSEL_SUFFIXES, FLAGS

load_dotenv()

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ]
)
log = structlog.get_logger()

DATABASE_URL = os.environ["DATABASE_URL"]
REDIS_URL    = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_CH     = "vessel:positions:live"
UPDATE_INTERVAL = 30  # seconds

_shutdown = asyncio.Event()

VESSEL_TYPE_NAMES = {
    70: "Cargo", 79: "Bulk Carrier", 80: "Tanker",
}


def _handle_signal(*_):
    _shutdown.set()


def generate_vessels(route: dict) -> list[dict]:
    """
    Spread `vessels_on_route` vessels evenly across a route's transit time
    so the lane looks fully populated at any moment.
    """
    legs      = _LEGS[route["route_id"]]
    total_nm  = legs[-1]["cum_end"]
    transit_h = total_nm / route["speed_kn"]
    n         = route["vessels_on_route"]
    base      = route["mmsi_base"]
    v_type    = route["vessel_type"]

    rng = random.Random(base)  # deterministic per route

    vessels = []
    for i in range(n):
        company = rng.choice(SHIPPING_COMPANIES)
        suffix  = rng.choice(VESSEL_SUFFIXES)
        name    = f"{company} {suffix}"
        flag    = rng.choice(FLAGS)

        # Evenly spaced base offset + small random jitter (±15% of spacing)
        base_offset = (transit_h / n) * i
        jitter      = rng.uniform(-transit_h / n * 0.15, transit_h / n * 0.15)
        offset      = base_offset + jitter

        # Lateral scatter: ±25 nm from centreline (simulates real lane spread)
        lateral = rng.uniform(-25.0, 25.0)

        # Speed variation: ±1.5 kn around nominal
        speed_var = rng.uniform(-1.5, 1.5)

        vessels.append({
            "mmsi":       base + i + 1,
            "name":       name,
            "flag":       flag,
            "type":       v_type,
            "type_name":  VESSEL_TYPE_NAMES.get(v_type, "Cargo"),
            "offset_h":   offset,
            "lateral_nm": lateral,
            "speed_var":  speed_var,
        })
    return vessels


# Pre-compute route geometry once at startup
_LEGS: dict[str, list[dict]] = {r["route_id"]: build_legs(r["waypoints"]) for r in ROUTES}

# Generate all vessel definitions once
_ALL_VESSELS: list[tuple[dict, dict]] = []  # (route, vessel)
for _route in ROUTES:
    for _v in generate_vessels(_route):
        _ALL_VESSELS.append((_route, _v))

log.info("vessels_generated", total=len(_ALL_VESSELS))


async def seed_vessel_metadata(pool: asyncpg.Pool):
    """Insert all simulated vessels into the vessels table."""
    await pool.executemany(
        """
        INSERT INTO vessels (mmsi, name, flag, vessel_type, vessel_type_name, updated_at)
        VALUES ($1, $2, $3, $4, $5, NOW())
        ON CONFLICT (mmsi) DO UPDATE SET
            name             = EXCLUDED.name,
            updated_at       = NOW()
        """,
        [
            (v["mmsi"], v["name"], v["flag"], v["type"], v["type_name"])
            for _, v in _ALL_VESSELS
        ],
    )
    log.info("vessel_metadata_seeded", total=len(_ALL_VESSELS))


async def tick(pool: asyncpg.Pool, redis: aioredis.Redis):
    """Compute current positions for all vessels, write to DB and Redis."""
    rows = []
    for route, vessel in _ALL_VESSELS:
        pos = current_position(
            waypoints=route["waypoints"],
            speed_kn=route["speed_kn"] + vessel.get("speed_var", 0),
            offset_hours=vessel["offset_h"],
            lateral_offset_nm=vessel.get("lateral_nm", 0.0),
            legs=_LEGS[route["route_id"]],
        )
        rows.append({
            "mmsi":    vessel["mmsi"],
            "lat":     pos.lat,
            "lon":     pos.lon,
            "speed":   pos.speed,
            "heading": pos.heading,
        })

    # Batch DB insert
    await pool.executemany(
        """
        INSERT INTO vessel_positions
            (time, mmsi, lat, lon, position, speed, heading, nav_status, source)
        VALUES
            (NOW(), $1, $2, $3,
             ST_SetSRID(ST_MakePoint($3, $2), 4326),
             $4, $5, 0, 'simulated')
        """,
        [(r["mmsi"], r["lat"], r["lon"], r["speed"], r["heading"]) for r in rows],
    )

    # Publish to Redis for live WebSocket push
    now_iso = datetime.now(tz=timezone.utc).isoformat()
    pipeline = redis.pipeline()
    for r in rows:
        payload = orjson.dumps({
            "mmsi":    r["mmsi"],
            "lat":     r["lat"],
            "lon":     r["lon"],
            "speed":   r["speed"],
            "heading": r["heading"],
            "time":    now_iso,
            "source":  "simulated",
        })
        pipeline.publish(REDIS_CH, payload)
    await pipeline.execute()

    log.info("simulator_tick", vessels=len(rows))


async def main():
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_signal)

    pool  = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    redis = aioredis.from_url(REDIS_URL, decode_responses=False)

    await seed_vessel_metadata(pool)

    log.info("simulator_running", vessels=len(_ALL_VESSELS), routes=len(ROUTES))
    while not _shutdown.is_set():
        try:
            await tick(pool, redis)
        except Exception:
            log.exception("tick_failed")
        try:
            await asyncio.wait_for(_shutdown.wait(), timeout=UPDATE_INTERVAL)
        except asyncio.TimeoutError:
            pass

    await pool.close()
    await redis.aclose()
    log.info("simulator_stopped")


if __name__ == "__main__":
    asyncio.run(main())
