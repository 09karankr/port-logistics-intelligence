# Real-Time Port & Logistics Intelligence System

Palantir-inspired global shipping intelligence platform with live AIS vessel tracking, risk scoring, port congestion detection, and automated alerting.

---

## What it does

- **Live vessel tracking** — ingests real AIS positions via [aisstream.io](https://aisstream.io) WebSocket for cargo and tanker vessels globally
- **Risk scoring** — composite 0–100 score per shipment: ETA deviation + port congestion + weather hazard
- **Port congestion detection** — counts stationary vessels in anchorage zones, benchmarks against 90-day baseline
- **Weather correlation** — OpenWeatherMap marine data overlaid on vessel paths
- **Automated alerts** — Slack + email when shipments cross risk thresholds
- **Historical analytics** — which ports are consistently late, which shipping lanes are riskiest by season

---

## Prerequisites

| Tool | Version |
|---|---|
| Docker + Docker Compose | v2.x |
| Node.js | 20.x (local dev only) |
| Python | 3.12 (local dev only) |

---

## Quick Start

### 1. Get API Keys (all free tier)

| Service | URL | Used for |
|---|---|---|
| aisstream.io | https://aisstream.io | Live AIS vessel positions |
| OpenWeatherMap | https://openweathermap.org/api | Marine weather |
| ~~Mapbox~~ | N/A | Map tiles — replaced by CARTO (no signup) |

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in your API keys
```

### 3. Launch with Docker

```bash
bash scripts/start.sh
```

Opens at **http://localhost:3000**

API docs at **http://localhost:8000/docs**

### 4. Seed synthetic orders (after ~2 minutes)

Wait for the AIS consumer to ingest some vessels, then:

```bash
docker compose exec celery_worker python db/seeds/synthetic_orders.py
```

This creates ~40 fictional purchase orders linked to real tracked vessels.

---

## Local Development (no Docker for app code)

```bash
cp .env.example .env
bash scripts/dev.sh
```

This starts DB + Redis in Docker and runs all Python/Node processes locally with hot-reload.

---

## Architecture

```
aisstream.io WebSocket
        │
        ▼
  AIS Consumer (Python asyncio)
        │  batch insert every 5s
        ▼
  TimescaleDB + PostGIS ◄──── Weather Poller (Celery beat, 30min)
        │                              ▲
        ▼                              │ OpenWeatherMap API
  Celery Worker (risk scoring, 10min)
        │
        ├──► risk_scores table
        │
        └──► Alert tasks ──► Slack / Email
                │
                ▼
          FastAPI (REST + WebSocket)
                │
                ├──► Redis pub/sub (live positions → WS clients)
                │
                ▼
         React + Mapbox GL JS
```

---

## Services

| Service | Port | Description |
|---|---|---|
| `db` | 5432 | TimescaleDB + PostGIS |
| `redis` | 6379 | Celery broker + WS pub/sub |
| `ais_consumer` | — | AIS WebSocket consumer |
| `celery_worker` | — | Risk scoring + alert dispatch |
| `celery_beat` | — | Scheduled tasks (weather, congestion) |
| `api` | 8000 | FastAPI REST + WebSocket |
| `frontend` | 3000 | React + Mapbox |

---

## API Reference

| Endpoint | Description |
|---|---|
| `GET /vessels/live` | All active vessels (GeoJSON-ready) |
| `GET /vessels/{mmsi}/track` | Historical track (last N hours) |
| `GET /vessels/{mmsi}/risk` | Current risk score + signal breakdown |
| `GET /ports/congestion/all` | Live congestion for all ports |
| `GET /orders` | Shipment orders (filterable) |
| `POST /orders` | Create a synthetic order |
| `GET /analytics/fleet-summary` | Dashboard stats |
| `GET /analytics/port-performance` | Port congestion rankings |
| `GET /analytics/lane-risk` | Risk by shipping lane + month |
| `GET /analytics/high-risk-shipments` | Active HIGH/MEDIUM risk list |
| `WS /ws/stream` | Live vessel position WebSocket |

Full interactive docs: http://localhost:8000/docs

---

## Risk Score Breakdown

| Signal | Max Points | Logic |
|---|---|---|
| ETA Delay | 40 | Log-scale: 1 day late → ~13 pts, 5 days → ~32 pts, 10 days → 40 pts |
| Port Congestion | 30 | Linear: congestion_pct × 0.30 |
| Weather Hazard | 30 | Wave ≥ 4m or wind ≥ 40 kn → 30 pts; moderate → proportional |

**LOW** < 40 · **MEDIUM** 40–70 · **HIGH** > 70

Alerts fire on threshold crossing with 4-hour cooldown per vessel.

---

## Stack

- **Ingestion**: Python asyncio WebSocket consumer, asyncpg
- **Storage**: TimescaleDB (time-series partitioning), PostGIS (geospatial), Redis
- **Processing**: Celery workers + beat scheduler
- **API**: FastAPI, asyncpg, Pydantic v2
- **Frontend**: React 18, MapLibre GL JS + CARTO tiles (no API key), Recharts, Zustand, TanStack Query
- **Infrastructure**: Docker Compose
