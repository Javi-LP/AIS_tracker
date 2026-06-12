-- 1. Número de barcos activos
SELECT
    COUNT(DISTINCT mmsi) AS active_vessels
FROM "MarineTraffic".position_report;


-- 2. Velocidad media general
SELECT
    ROUND(AVG(sog)::numeric, 2) AS avg_speed
FROM "MarineTraffic".position_report
WHERE sog IS NOT NULL;


-- 3. Distribución por estado de movimiento
SELECT
    movement_status,
    COUNT(*) AS total_messages,
    COUNT(DISTINCT mmsi) AS vessels
FROM "MarineTraffic".position_report_enriched
GROUP BY movement_status
ORDER BY total_messages DESC;


-- 4. Mensajes por hora
SELECT
    hour,
    total_messages,
    active_vessels,
    avg_speed,
    stopped_vessels,
    moving_vessels
FROM "MarineTraffic".kpi_hourly_traffic
ORDER BY hour DESC
LIMIT 24;


-- 5. Calidad de datos
SELECT
    quality_status,
    COUNT(*) AS records
FROM "MarineTraffic".position_quality_check
GROUP BY quality_status
ORDER BY records DESC;


-- 6. Top 10 barcos con más posiciones registradas
SELECT
    mmsi,
    MAX(ship_name) AS ship_name,
    COUNT(*) AS position_messages,
    ROUND(AVG(sog)::numeric, 2) AS avg_speed
FROM "MarineTraffic".position_report
GROUP BY mmsi
ORDER BY position_messages DESC
LIMIT 10;


-- 7. Distribución por tipo de barco
SELECT
    ship_type,
    vessels,
    position_messages,
    avg_speed
FROM "MarineTraffic".kpi_ship_type_distribution
ORDER BY vessels DESC;
