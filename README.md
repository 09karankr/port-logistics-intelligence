# Real-Time Port & Logistics Intelligence System

> A Palantir-inspired maritime intelligence platform that tracks real vessels live on a global map, scores shipment delivery risk in real time, and fires automated Slack alerts when something goes wrong.

**[Live Demo](https://port-logistics-intelligence-ten.vercel.app)** · **[Demo Video](#)** · Built by [Karan Kumar](https://github.com/09karankr)

---

## The Problem

When a $200M shipment leaves Shanghai, the retailer has zero visibility into whether it arrives on time. Port congestion, typhoons, and customs delays make ETA unpredictable. This system gives operations teams a live situational picture and early warnings before delays become crises — the same way Palantir, Flexport, and Project44 do it.

---

## What It Does

| Feature | Description |
|---|---|
| **Live vessel tracking** | Ingests real AIS (ship GPS transponder) data via WebSocket — the same signal coast guards use |
| **Global lane simulation** | 1,400+ synthetic vessels sail realistic great-circle routes across trans-Pacific, Suez, Atlantic lanes |
| **Risk scoring** | Every 10 min: scores each shipment 0–100 across ETA delay, port congestion, and weather hazard |
| **Port congestion detection** | Counts vessels stationary in anchorage zones via PostGIS spatial queries, benchmarks against 90-day baseline |
| **Weather correlation** | OpenWeatherMap marine data overlaid on vessel projected paths |
| **Automated alerts** | Slack + email fires when a shipment crosses HIGH (>70) or MEDIUM (>40) risk threshold |
| **Historical analytics** | Which ports are consistently late? Which shipping lanes are riskiest by season? |

---

## Risk Score Breakdown

```
ETA Delay Score     0–40 pts  →  how many days late vs scheduled delivery
Port Congestion     0–30 pts  →  anchored vessel count vs 90-day baseline
Weather Hazard      0–30 pts  →  wave height / wind speed on projected path
─────────────────────────────────────────────────────────────────────
Total 0–100   →   LOW / MEDIUM / HIGH
```

---

## Architecture

```
aisstream.io WebSocket (real AIS)
        │
        ▼
  AIS Consumer ←──────────────── Vessel Simulator (1,400+ synthetic ships)
  (Python asyncio)                (great-circle routes, 30s updates)
        │
        └──────────────┬────────────────────────┘
                       │ batch insert
                       ▼
              TimescaleDB + PostGIS
              (time-series + geospatial)
                       │
          ┌────────────┼──────────────┐
          ▼            ▼              ▼
    Risk Engine    Weather         Congestion
    (Celery,       Poller          Detector
     10 min)       (30 min)        (15 min)
          │
          └──→ Alert Tasks ──→ Slack / Email
                       │
                 FastAPI (REST + WebSocket)
                       │
              Redis pub/sub (live position fan-out)
                       │
              React + MapLibre GL JS
```

---

## Tech Stack & Why

| Layer | Technology | Why |
|---|---|---|
| **AIS ingestion** | Python asyncio + websockets | Non-blocking WebSocket consumer handles thousands of messages/sec without threads |
| **Time-series DB** | TimescaleDB (PostgreSQL extension) | Auto-partitions position data by time, compresses old chunks, continuous aggregates for analytics — same stack used by enterprise fleet platforms |
| **Geospatial** | PostGIS | Native SQL spatial queries: "count vessels within 10nm of port", great-circle distance, spatial indexing |
| **Task queue** | Celery + Redis | Distributed background workers for risk scoring, weather polling, alert dispatch — decoupled from the API |
| **API** | FastAPI | Async Python, auto-generates OpenAPI docs, native WebSocket support |
| **Live push** | Redis pub/sub | AIS consumer publishes positions → API subscribes → pushes to all browser clients. Decouples producer from consumers |
| **Map** | MapLibre GL JS + CARTO tiles | Open-source Mapbox fork, no API key required. GPU-rendered GL layers handle 10K+ vessel dots at 60fps |
| **Frontend state** | Zustand | Minimal global store for vessel positions — avoids Redux boilerplate for a single shared data source |
| **Infrastructure** | Docker Compose | All 7 services (DB, Redis, API, Celery worker, Celery beat, AIS consumer, simulator) wired together with health checks |

---

## Data Sources

| Source | What it provides | Cost |
|---|---|---|
| [aisstream.io](https://aisstream.io) | Live WebSocket feed of real vessel GPS positions | Free tier |
| [OpenWeatherMap](https://openweathermap.org/api) | Marine weather — wind speed, storm alerts | Free tier |
| [CARTO Basemaps](https://carto.com/basemaps) | Dark map tiles | Free, no account |
| Built-in simulator | 1,400+ vessels on real shipping lane routes | Custom-built |

---

## Run Locally

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop) (running)
- [Git](https://git-scm.com)

### 1. Clone and configure

```bash
git clone https://github.com/09karankr/port-logistics-intelligence.git
cd port-logistics-intelligence
cp .env.example .env
```

Open `.env` and fill in:
```env
AISSTREAM_API_KEY=    # free at aisstream.io
OPENWEATHER_API_KEY=  # free at openweathermap.org
SLACK_WEBHOOK_URL=    # optional — for alerts
```

### 2. Start everything

```bash
bash scripts/start.sh
```

This starts all 7 Docker services. First run takes ~3 min to pull images.

### 3. Seed the database

Wait ~2 minutes for the AIS consumer to ingest vessels, then:

```bash
docker compose exec celery_worker python db/seeds/synthetic_orders.py
```

### 4. Open the app

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| API docs | http://localhost:8000/docs |

### 5. Trigger risk scoring (optional — runs automatically every 10 min)

```bash
docker compose exec celery_worker celery -A celery_app.app call celery_app.tasks.risk_scoring.score_all_active_vessels
```

### Stop

```bash
docker compose down
```

---

## Share a Live Demo

To share the running app with someone outside your network:

```bash
# 1. Start the backend
docker compose up -d

# 2. Open a public tunnel
cloudflared tunnel --url http://localhost:8000
# Copy the printed URL: https://xxxx.trycloudflare.com

# 3. Set VITE_API_URL in Vercel → Settings → Environment Variables
#    Then redeploy

# 4. Share: https://port-logistics-intelligence-ten.vercel.app
```

> The cloudflared URL changes each session, so repeat steps 2–3 each time.

---

## Services Overview

| Container | Role |
|---|---|
| `portintel_db` | TimescaleDB + PostGIS (port 5432) |
| `portintel_redis` | Celery broker + WebSocket pub/sub |
| `portintel_ais` | AIS WebSocket consumer |
| `portintel_simulator` | Synthetic vessel position engine |
| `portintel_celery_worker` | Risk scoring + alert dispatch |
| `portintel_celery_beat` | Scheduled task runner (weather, congestion) |
| `portintel_api` | FastAPI REST + WebSocket (port 8000) |
| `portintel_frontend` | React + MapLibre GL (port 3000) |
