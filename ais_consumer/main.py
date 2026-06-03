"""
AIS WebSocket consumer.

Connects to aisstream.io, filters cargo/tanker vessels, batch-inserts
positions into TimescaleDB, and publishes live positions to Redis
pub/sub so the FastAPI WebSocket layer can push to browser clients.
"""

import asyncio
import json
import signal
import sys
from datetime import datetime, timezone

import orjson
import redis.asyncio as aioredis
import structlog
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_never,
    wait_exponential,
)

from config import (
    AISSTREAM_API_KEY,
    AISSTREAM_WS_URL,
    BATCH_SIZE,
    BATCH_TIMEOUT_SECONDS,
    BOUNDING_BOXES,
    REDIS_POSITIONS_CHANNEL,
    REDIS_URL,
    TRACKED_VESSEL_TYPES,
)
from db import bulk_insert_positions, close_pool, get_pool, upsert_vessel
from parser import parse_position_report

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ]
)
log = structlog.get_logger()

_shutdown = asyncio.Event()


def _handle_signal(*_):
    log.info("shutdown_signal_received")
    _shutdown.set()


async def publish_position(redis_client: aioredis.Redis, pos: dict):
    payload = orjson.dumps(
        {
            "mmsi":    pos["mmsi"],
            "lat":     pos["lat"],
            "lon":     pos["lon"],
            "speed":   pos.get("speed"),
            "heading": pos.get("heading"),
            "nav_status": pos.get("nav_status"),
            "time":    pos["time"].isoformat(),
        }
    )
    await redis_client.publish(REDIS_POSITIONS_CHANNEL, payload)


async def flush_batch(pool, redis_client, batch: list[dict]):
    if not batch:
        return
    try:
        await bulk_insert_positions(pool, batch)
        for pos in batch:
            await publish_position(redis_client, pos)
        log.info("batch_flushed", count=len(batch))
    except Exception:
        log.exception("batch_flush_failed", count=len(batch))


@retry(
    retry=retry_if_exception_type((
        ConnectionClosed,
        WebSocketException,
        OSError,
    )),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_never,
    reraise=False,
)
async def consume(pool, redis_client):
    subscribe_msg = {
        "APIKey":       AISSTREAM_API_KEY,
        "BoundingBoxes": BOUNDING_BOXES,
        "FilterMessageTypes": [
            "PositionReport",
            "ShipStaticData",
            "StandardClassBPositionReport",
            "ExtendedClassBPositionReport",
        ],
    }

    log.info("connecting_to_aisstream", url=AISSTREAM_WS_URL)

    async with websockets.connect(
        AISSTREAM_WS_URL,
        ping_interval=20,
        ping_timeout=30,
        max_size=2**20,
    ) as ws:
        await ws.send(json.dumps(subscribe_msg))
        log.info("subscribed", bounding_boxes=len(BOUNDING_BOXES))

        batch: list[dict] = []
        last_flush = asyncio.get_event_loop().time()
        vessel_cache: set[int] = set()  # avoid redundant vessel upserts

        async def maybe_flush():
            nonlocal last_flush
            elapsed = asyncio.get_event_loop().time() - last_flush
            if len(batch) >= BATCH_SIZE or elapsed >= BATCH_TIMEOUT_SECONDS:
                await flush_batch(pool, redis_client, batch)
                batch.clear()
                last_flush = asyncio.get_event_loop().time()

        while not _shutdown.is_set():
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=BATCH_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                await maybe_flush()
                continue

            try:
                msg = orjson.loads(raw)
            except orjson.JSONDecodeError:
                continue

            pos = parse_position_report(msg)
            if pos is None:
                continue

            # Filter by vessel type only if TRACKED_VESSEL_TYPES is non-empty
            if TRACKED_VESSEL_TYPES:
                v_type = pos["vessel"].get("vessel_type", 0)
                if v_type and v_type not in TRACKED_VESSEL_TYPES:
                    continue

            # Upsert vessel metadata once per session per MMSI
            mmsi = pos["mmsi"]
            if mmsi not in vessel_cache:
                try:
                    await upsert_vessel(pool, pos["vessel"])
                    vessel_cache.add(mmsi)
                    if len(vessel_cache) % 100 == 0:
                        log.info("vessel_cache_size", size=len(vessel_cache))
                except Exception:
                    log.exception("vessel_upsert_failed", mmsi=mmsi)

            batch.append(pos)
            await maybe_flush()

        # Final flush before exit
        await flush_batch(pool, redis_client, batch)


async def main():
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_signal)

    pool = await get_pool()
    redis_client = aioredis.from_url(REDIS_URL, decode_responses=False)

    log.info("ais_consumer_started")
    try:
        await consume(pool, redis_client)
    finally:
        await close_pool()
        await redis_client.aclose()
        log.info("ais_consumer_stopped")


if __name__ == "__main__":
    asyncio.run(main())
