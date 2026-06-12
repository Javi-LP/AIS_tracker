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
