#!/usr/bin/env bash
# Full startup script — copy .env.example → .env first, fill in API keys.
set -euo pipefail

if [ ! -f .env ]; then
    echo "ERROR: .env file not found. Copy .env.example → .env and fill in your API keys."
    exit 1
fi

echo "==> Pulling latest images..."
docker compose pull db redis

echo "==> Starting database and Redis..."
docker compose up -d db redis

echo "==> Waiting for DB to be ready..."
until docker compose exec -T db pg_isready -U portintel -d portintel 2>/dev/null; do
    sleep 1
done
echo "    DB ready."

echo "==> Building services..."
docker compose build ais_consumer celery_worker celery_beat api frontend

echo "==> Starting all services..."
docker compose up -d

echo ""
echo "============================================"
echo "  Port Intelligence System — RUNNING"
echo "============================================"
echo "  Frontend:  http://localhost:3000"
echo "  API docs:  http://localhost:8000/docs"
echo "  API:       http://localhost:8000"
echo ""
echo "  To seed synthetic orders (after ~2 min):"
echo "    docker compose exec celery_worker python db/seeds/synthetic_orders.py"
echo ""
echo "  View logs:"
echo "    docker compose logs -f ais_consumer"
echo "    docker compose logs -f celery_worker"
echo "============================================"
