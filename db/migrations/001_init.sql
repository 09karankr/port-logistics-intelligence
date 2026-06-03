-- Enable extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─────────────────────────────────────────────
-- Static reference tables
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS vessels (
    mmsi          BIGINT PRIMARY KEY,
    name          TEXT,
    imo           BIGINT,
    call_sign     TEXT,
    vessel_type   INT,
    vessel_type_name TEXT,
    flag          TEXT,
    length        FLOAT,
    width         FLOAT,
    deadweight    FLOAT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ports (
    id            SERIAL PRIMARY KEY,
    name          TEXT NOT NULL,
    country       TEXT,
    un_locode     TEXT UNIQUE,
    -- Polygon defining the port water area (anchorage + berth zone)
    boundary      GEOMETRY(POLYGON, 4326),
    -- Inner circle used for "at-berth" detection
    berth_center  GEOMETRY(POINT, 4326),
    berth_radius_nm FLOAT DEFAULT 2.0,
    -- Outer anchorage zone used for congestion detection
    anchorage_center GEOMETRY(POINT, 4326),
    anchorage_radius_nm FLOAT DEFAULT 10.0,
    timezone      TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ports_boundary ON ports USING GIST (boundary);
CREATE INDEX IF NOT EXISTS idx_ports_berth ON ports USING GIST (berth_center);
CREATE INDEX IF NOT EXISTS idx_ports_anchorage ON ports USING GIST (anchorage_center);

CREATE TABLE IF NOT EXISTS shipping_lanes (
    id            SERIAL PRIMARY KEY,
    name          TEXT NOT NULL,
    origin_port   INT REFERENCES ports(id),
    dest_port     INT REFERENCES ports(id),
    path          GEOMETRY(LINESTRING, 4326),
    avg_transit_days FLOAT
);

-- ─────────────────────────────────────────────
-- Time-series: vessel positions (hypertable)
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS vessel_positions (
    time          TIMESTAMPTZ NOT NULL,
    mmsi          BIGINT NOT NULL,
    lat           DOUBLE PRECISION NOT NULL,
    lon           DOUBLE PRECISION NOT NULL,
    position      GEOMETRY(POINT, 4326),
    speed         FLOAT,          -- knots
    heading       FLOAT,          -- degrees
    course        FLOAT,          -- degrees
    nav_status    INT,            -- AIS navigational status code
    draught       FLOAT,          -- meters
    destination   TEXT,
    eta_ais       TIMESTAMPTZ,    -- ETA reported by vessel AIS transponder
    source        TEXT DEFAULT 'aisstream'
);

SELECT create_hypertable('vessel_positions', 'time', if_not_exists => TRUE);

-- Spatial index on the geometry column
CREATE INDEX IF NOT EXISTS idx_vp_position ON vessel_positions USING GIST (position);
CREATE INDEX IF NOT EXISTS idx_vp_mmsi_time ON vessel_positions (mmsi, time DESC);

-- Compression: compress chunks older than 7 days
ALTER TABLE vessel_positions SET (
    timescaledb.compress,
    timescaledb.compress_orderby = 'time DESC',
    timescaledb.compress_segmentby = 'mmsi'
);
SELECT add_compression_policy('vessel_positions', INTERVAL '7 days', if_not_exists => TRUE);

-- ─────────────────────────────────────────────
-- Synthetic shipment orders
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS shipment_orders (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_ref       TEXT UNIQUE NOT NULL,
    customer        TEXT NOT NULL,
    commodity       TEXT,
    value_usd       BIGINT,         -- order value in USD cents
    origin_port     INT REFERENCES ports(id),
    dest_port       INT REFERENCES ports(id),
    vessel_mmsi     BIGINT REFERENCES vessels(mmsi),
    scheduled_etd   TIMESTAMPTZ,    -- scheduled departure
    scheduled_eta   TIMESTAMPTZ,    -- committed delivery date
    actual_etd      TIMESTAMPTZ,
    status          TEXT NOT NULL DEFAULT 'in_transit'
                        CHECK (status IN ('pending', 'in_transit', 'arrived', 'delayed', 'cancelled')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_orders_vessel ON shipment_orders (vessel_mmsi);
CREATE INDEX IF NOT EXISTS idx_orders_status ON shipment_orders (status);

-- ─────────────────────────────────────────────
-- Risk scores (time-series, one row per scoring run)
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS risk_scores (
    time                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    mmsi                BIGINT NOT NULL,
    order_id            UUID REFERENCES shipment_orders(id),
    total_score         FLOAT NOT NULL,
    risk_level          TEXT NOT NULL CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH')),
    -- Signal breakdown
    eta_delay_days      FLOAT,
    eta_score           FLOAT,
    congestion_pct      FLOAT,
    congestion_score    FLOAT,
    weather_max_wave_m  FLOAT,
    weather_score       FLOAT,
    -- Human-readable explanation
    summary             TEXT,
    -- Alert state
    alert_sent          BOOLEAN DEFAULT FALSE,
    alert_sent_at       TIMESTAMPTZ
);

SELECT create_hypertable('risk_scores', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_rs_mmsi_time ON risk_scores (mmsi, time DESC);

-- ─────────────────────────────────────────────
-- Weather grid snapshots
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS weather_snapshots (
    time            TIMESTAMPTZ NOT NULL,
    lat             FLOAT NOT NULL,
    lon             FLOAT NOT NULL,
    position        GEOMETRY(POINT, 4326),
    wave_height_m   FLOAT,
    wind_speed_ms   FLOAT,
    wind_direction  FLOAT,
    pressure_hpa    FLOAT,
    storm_alert     BOOLEAN DEFAULT FALSE,
    description     TEXT,
    source          TEXT DEFAULT 'openweathermap'
);

SELECT create_hypertable('weather_snapshots', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_ws_position ON weather_snapshots USING GIST (position);
CREATE INDEX IF NOT EXISTS idx_ws_time ON weather_snapshots (time DESC);

-- ─────────────────────────────────────────────
-- Port congestion snapshots (materialized per scoring run)
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS port_congestion (
    time                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    port_id             INT NOT NULL REFERENCES ports(id),
    vessels_anchored    INT DEFAULT 0,   -- stationary in anchorage zone
    vessels_at_berth    INT DEFAULT 0,
    vessels_inbound     INT DEFAULT 0,
    congestion_pct      FLOAT,           -- 0–100 relative to 90-day baseline
    baseline_anchored   FLOAT            -- rolling 90-day avg
);

SELECT create_hypertable('port_congestion', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_pc_port_time ON port_congestion (port_id, time DESC);

-- ─────────────────────────────────────────────
-- Alert log
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS alert_log (
    id              SERIAL PRIMARY KEY,
    sent_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    mmsi            BIGINT,
    order_id        UUID REFERENCES shipment_orders(id),
    channel         TEXT NOT NULL CHECK (channel IN ('email', 'slack', 'webhook')),
    risk_level      TEXT,
    message         TEXT,
    delivered       BOOLEAN DEFAULT FALSE,
    error           TEXT
);

-- ─────────────────────────────────────────────
-- Continuous aggregates for analytics
-- ─────────────────────────────────────────────

-- Hourly position summary per vessel (used for track replay + speed analytics)
CREATE MATERIALIZED VIEW IF NOT EXISTS vessel_hourly_summary
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    mmsi,
    AVG(speed)                  AS avg_speed,
    MAX(speed)                  AS max_speed,
    COUNT(*)                    AS position_count,
    LAST(lat, time)             AS last_lat,
    LAST(lon, time)             AS last_lon,
    LAST(nav_status, time)      AS last_nav_status
FROM vessel_positions
GROUP BY bucket, mmsi
WITH NO DATA;

SELECT add_continuous_aggregate_policy('vessel_hourly_summary',
    start_offset  => INTERVAL '3 hours',
    end_offset    => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

-- Daily port congestion average (for historical analytics)
CREATE MATERIALIZED VIEW IF NOT EXISTS port_congestion_daily
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS bucket,
    port_id,
    AVG(congestion_pct)        AS avg_congestion_pct,
    MAX(congestion_pct)        AS peak_congestion_pct,
    AVG(vessels_anchored)      AS avg_vessels_anchored
FROM port_congestion
GROUP BY bucket, port_id
WITH NO DATA;

SELECT add_continuous_aggregate_policy('port_congestion_daily',
    start_offset  => INTERVAL '3 days',
    end_offset    => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- ─────────────────────────────────────────────
-- Seed: major world ports
-- ─────────────────────────────────────────────

INSERT INTO ports (name, country, un_locode, berth_center, berth_radius_nm, anchorage_center, anchorage_radius_nm)
VALUES
    ('Port of Los Angeles',     'US', 'USLAX',
        ST_SetSRID(ST_MakePoint(-118.2720, 33.7298), 4326), 3.0,
        ST_SetSRID(ST_MakePoint(-118.1800, 33.7100), 4326), 12.0),
    ('Port of Long Beach',      'US', 'USLGB',
        ST_SetSRID(ST_MakePoint(-118.2167, 33.7542), 4326), 3.0,
        ST_SetSRID(ST_MakePoint(-118.1500, 33.7400), 4326), 12.0),
    ('Port of Shanghai',        'CN', 'CNSHA',
        ST_SetSRID(ST_MakePoint(121.8714, 31.3861), 4326), 5.0,
        ST_SetSRID(ST_MakePoint(122.1000, 31.2000), 4326), 15.0),
    ('Port of Singapore',       'SG', 'SGSIN',
        ST_SetSRID(ST_MakePoint(103.8565, 1.2655), 4326), 4.0,
        ST_SetSRID(ST_MakePoint(103.9000, 1.2000), 4326), 12.0),
    ('Port of Rotterdam',       'NL', 'NLRTM',
        ST_SetSRID(ST_MakePoint(4.0543, 51.9060), 4326), 4.0,
        ST_SetSRID(ST_MakePoint(4.2000, 51.8800), 4326), 15.0),
    ('Port of Hamburg',         'DE', 'DEHAM',
        ST_SetSRID(ST_MakePoint(9.9937, 53.5389), 4326), 3.0,
        ST_SetSRID(ST_MakePoint(8.8000, 54.0000), 4326), 15.0),
    ('Port of Busan',           'KR', 'KRPUS',
        ST_SetSRID(ST_MakePoint(129.0756, 35.0948), 4326), 3.0,
        ST_SetSRID(ST_MakePoint(129.1500, 35.0500), 4326), 12.0),
    ('Port of Ningbo-Zhoushan', 'CN', 'CNNGB',
        ST_SetSRID(ST_MakePoint(121.8867, 29.8683), 4326), 4.0,
        ST_SetSRID(ST_MakePoint(122.0000, 29.7000), 4326), 12.0),
    ('Port of Shenzhen',        'CN', 'CNSZX',
        ST_SetSRID(ST_MakePoint(113.8547, 22.5095), 4326), 3.0,
        ST_SetSRID(ST_MakePoint(114.0000, 22.4000), 4326), 10.0),
    ('Port of Antwerp',         'BE', 'BEANR',
        ST_SetSRID(ST_MakePoint(4.4059, 51.2213), 4326), 3.0,
        ST_SetSRID(ST_MakePoint(4.0000, 51.4000), 4326), 15.0),
    ('Port of Hong Kong',       'HK', 'HKHKG',
        ST_SetSRID(ST_MakePoint(114.1694, 22.3193), 4326), 3.0,
        ST_SetSRID(ST_MakePoint(114.2000, 22.2500), 4326), 10.0),
    ('Port of Jebel Ali',       'AE', 'AEJEA',
        ST_SetSRID(ST_MakePoint(55.0272, 24.9857), 4326), 4.0,
        ST_SetSRID(ST_MakePoint(55.1000, 24.9000), 4326), 12.0),
    ('Port of Tanjung Pelepas', 'MY', 'MYPGU',
        ST_SetSRID(ST_MakePoint(103.5500, 1.3667), 4326), 3.0,
        ST_SetSRID(ST_MakePoint(103.5000, 1.3000), 4326), 10.0),
    ('Port of Qingdao',         'CN', 'CNTAO',
        ST_SetSRID(ST_MakePoint(120.3826, 36.0671), 4326), 3.0,
        ST_SetSRID(ST_MakePoint(120.4500, 36.0000), 4326), 10.0),
    ('Port of Tianjin',         'CN', 'CNTXG',
        ST_SetSRID(ST_MakePoint(117.8076, 38.9858), 4326), 3.0,
        ST_SetSRID(ST_MakePoint(118.0000, 38.9000), 4326), 12.0)
ON CONFLICT DO NOTHING;
