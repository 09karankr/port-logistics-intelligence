FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc && \
    rm -rf /var/lib/apt/lists/*

COPY celery_app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire repo so celery can import from root packages
COPY . .

ENV PYTHONPATH=/app
