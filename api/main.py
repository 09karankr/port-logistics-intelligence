import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.core.config import get_settings
from api.core.db import init_pool, close_pool
from api.core.redis import init_redis, close_redis
from api.routers import vessels, ports, orders, analytics, stream

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ]
)
log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("api_starting")
    await init_pool()
    await init_redis()
    yield
    await close_pool()
    await close_redis()
    log.info("api_stopped")


settings = get_settings()

app = FastAPI(
    title="Port & Logistics Intelligence API",
    version="1.0.0",
    description="Real-time vessel tracking, risk scoring, and port analytics",
    lifespan=lifespan,
    redirect_slashes=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(vessels.router)
app.include_router(ports.router)
app.include_router(orders.router)
app.include_router(analytics.router)
app.include_router(stream.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
