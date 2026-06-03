#!/usr/bin/env bash
# Local development — runs DB and Redis in Docker, everything else natively.
set -euo pipefail

if [ ! -f .env ]; then
    echo "ERROR: .env not found."
    exit 1
fi

source .env

echo "==> Starting DB + Redis..."
docker compose up -d db redis
until docker compose exec -T db pg_isready -U portintel -d portintel 2>/dev/null; do sleep 1; done

echo "==> Installing Python deps (AIS consumer)..."
(cd ais_consumer && pip install -r requirements.txt -q)

echo "==> Installing Python deps (Celery)..."
pip install -r celery_app/requirements.txt -q

echo "==> Installing Python deps (API)..."
(cd api && pip install -r requirements.txt -q)

echo "==> Installing frontend deps..."
(cd frontend && npm install --silent)

echo ""
echo "Starting all processes (Ctrl+C to stop all):"
echo ""

# Use trap to kill all child processes on exit
trap 'kill $(jobs -p) 2>/dev/null' EXIT

# AIS Consumer
(cd ais_consumer && python main.py) &
echo "  [AIS Consumer]   started"

# Celery worker
celery -A celery_app.app worker --loglevel=info --concurrency=2 &
echo "  [Celery Worker]  started"

# Celery beat
celery -A celery_app.app beat --loglevel=info &
echo "  [Celery Beat]    started"

# FastAPI
uvicorn api.main:app --reload --port 8000 &
echo "  [API]            http://localhost:8000"

# React frontend
(cd frontend && npm run dev) &
echo "  [Frontend]       http://localhost:3000"

wait
