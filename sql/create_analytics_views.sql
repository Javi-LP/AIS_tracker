CREATE OR REPLACE VIEW "MarineTraffic".position_report_enriched AS
SELECT
    id,
    mmsi,
    ship_name,
    latitude,
    longitude,
    sog,
    cog,
    nav_status,
    time_utc,
    inserted_at,
    CASE
        WHEN sog IS NULL THEN 'unknown'
        WHEN sog < 0.5 THEN 'stopped'
        WHEN sog BETWEEN 0.5 AND 5 THEN 'slow_movement'
        ELSE 'active_navigation'
    END AS movement_status
FROM "MarineTraffic".position_report;


CREATE OR REPLACE VIEW "MarineTraffic".position_quality_check AS
SELECT
    id,
    mmsi,
    ship_name,
    latitude,
    longitude,
    sog,
    cog,
    nav_status,
    time_utc,
    CASE
        WHEN latitude NOT BETWEEN -90 AND 90 THEN 'invalid_latitude'
        WHEN longitude NOT BETWEEN -180 AND 180 THEN 'invalid_longitude'
        WHEN sog < 0 THEN 'invalid_speed'
        WHEN sog > 60 THEN 'very_high_speed'
        ELSE 'valid'
    END AS quality_status
FROM "MarineTraffic".position_report;


CREATE OR REPLACE VIEW "MarineTraffic".kpi_hourly_traffic AS
SELECT
    date_trunc('hour', time_utc) AS hour,
    COUNT(*) AS total_messages,
    COUNT(DISTINCT mmsi) AS active_vessels,
    ROUND(AVG(sog)::numeric, 2) AS avg_speed,
    COUNT(DISTINCT CASE WHEN sog < 0.5 THEN mmsi END) AS stopped_vessels,
    COUNT(DISTINCT CASE WHEN sog >= 0.5 THEN mmsi END) AS moving_vessels
FROM "MarineTraffic".position_report
GROUP BY date_trunc('hour', time_utc)
ORDER BY hour DESC;


CREATE OR REPLACE VIEW "MarineTraffic".kpi_ship_type_distribution AS
SELECT
    s.ship_type,
    COUNT(DISTINCT p.mmsi) AS vessels,
    COUNT(*) AS position_messages,
    ROUND(AVG(p.sog)::numeric, 2) AS avg_speed
FROM "MarineTraffic".position_report p
LEFT JOIN "MarineTraffic".ais_ship_static_data s
    ON p.mmsi = s.mmsi
GROUP BY s.ship_type
ORDER BY vessels DESC;
