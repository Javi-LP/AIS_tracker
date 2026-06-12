CREATE SCHEMA IF NOT EXISTS "MarineTraffic";

CREATE TABLE IF NOT EXISTS "MarineTraffic".ais_ship_static_data (
    mmsi BIGINT PRIMARY KEY,
    callsign VARCHAR(255),
    ship_name VARCHAR(255),
    ship_type INTEGER,
    draught FLOAT,
    length FLOAT,
    width FLOAT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS "MarineTraffic".position_report (
    id SERIAL PRIMARY KEY,
    mmsi BIGINT,
    ship_name VARCHAR(255),
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    sog FLOAT,
    cog FLOAT,
    nav_status INTEGER,
    time_utc TIMESTAMP WITH TIME ZONE NOT NULL,
    inserted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS "MarineTraffic".monitoring_zones (
    id SERIAL PRIMARY KEY,
    zone_name VARCHAR(255) NOT NULL,
    lat_min DOUBLE PRECISION NOT NULL,
    lon_min DOUBLE PRECISION NOT NULL,
    lat_max DOUBLE PRECISION NOT NULL,
    lon_max DOUBLE PRECISION NOT NULL,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO "MarineTraffic".monitoring_zones (name, lat_min, lon_min, lat_max, lon_max)
VALUES 
    ('Suez_South_Entrance', 29.75, 32.40, 30.10, 32.70),
    ('Gibraltar_Strait', 35.85, -5.60, 36.15, -5.20),
    ('English_Channel_Calais', 50.90, 1.40, 51.10, 1.95),
    ('Constanta_Danube_Canal', 44.05, 28.55, 44.25, 28.75),
    ('Arles_Rhone_River', 43.30, 4.75, 43.60, 5.05),
    ('Danish_Straits', 57.60, 10.40, 57.95, 10.85),
    ('Bosphorus_Strait', 41.00, 28.95, 41.30, 29.15);
