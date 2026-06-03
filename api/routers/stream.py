"""
WebSocket endpoint that pushes live vessel position updates to browser clients.

Architecture:
  AIS consumer → Redis pub/sub (vessel:positions:live)
  FastAPI WS handler → subscribes to Redis → pushes JSON frames to each connected client

Each client receives all vessel updates. The frontend uses the MMSI
to update the correct marker on the Mapbox map.
"""

import asyncio
import json

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import redis.asyncio as aioredis

from api.core.redis import get_redis

router = APIRouter(tags=["stream"])
log = structlog.get_logger()

CHANNEL = "vessel:positions:live"


@router.websocket("/ws/stream")
async def vessel_stream(websocket: WebSocket):
    await websocket.accept()
    redis = get_redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe(CHANNEL)
    log.info("ws_client_connected", client=websocket.client)

    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            data = message["data"]
            if isinstance(data, bytes):
                data = data.decode()
            await websocket.send_text(data)
    except WebSocketDisconnect:
        log.info("ws_client_disconnected", client=websocket.client)
    except Exception:
        log.exception("ws_error")
    finally:
        await pubsub.unsubscribe(CHANNEL)
        await pubsub.aclose()
