\timing on

\echo '============================================================'
\echo 'KPIs PARA PROYECTO AIS EN AWS'
\echo '============================================================'

\echo ''
\echo '1. KPIs de coste y eficiencia'
\echo '------------------------------------------------------------'

\echo ''
\echo 'KPI 1.1 - Volumen total procesado'
\echo 'Este KPI sirve como denominador para calcular coste medio por carga de trabajo.'
SELECT
    COUNT(*) AS total_position_messages,
    COUNT(DISTINCT mmsi) AS total_unique_vessels,
    MIN(time_utc) AS first_message_time,
    MAX(time_utc) AS last_message_time
FROM "MarineTraffic".position_report;

\echo ''
\echo 'KPI 1.2 - Volumen de registros por tabla'
\echo 'Permite estimar qué tablas concentran el almacenamiento del proyecto.'
SELECT
    'ais_ship_static_data' AS table_name,
    COUNT(*) AS records
FROM "MarineTraffic".ais_ship_static_data
UNION ALL
SELECT
    'position_report' AS table_name,
    COUNT(*) AS records
FROM "MarineTraffic".position_report
UNION ALL
SELECT
    'monitoring_zones' AS table_name,
    COUNT(*) AS records
FROM "MarineTraffic".monitoring_zones
ORDER BY records DESC;

\echo ''
\echo 'KPI 1.3 - Tamaño ocupado por tablas del esquema MarineTraffic'
\echo 'Aproxima el coste de almacenamiento dentro de PostgreSQL/RDS.'
SELECT
    relname AS table_name,
    pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
    pg_total_relation_size(relid) AS total_size_bytes
FROM pg_catalog.pg_statio_user_tables
WHERE schemaname = 'MarineTraffic'
ORDER BY pg_total_relation_size(relid) DESC;

\echo ''
\echo 'KPI 1.4 - Zonas de monitorización configuradas'
\echo 'Permite controlar si hay zonas activas consumiendo datos del stream.'
SELECT
    COUNT(*) AS total_zones,
    COUNT(*) FILTER (WHERE active = TRUE) AS active_zones,
    COUNT(*) FILTER (WHERE active = FALSE) AS inactive_zones
FROM "MarineTraffic".monitoring_zones;


\echo ''
\echo '2. KPIs de rendimiento y velocidad'
\echo '------------------------------------------------------------'

\echo ''
\echo 'KPI 2.1 - Mensajes AIS por hora'
\echo 'Permite medir la carga de trabajo y la tasa de crecimiento temporal.'
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

\echo ''
\echo 'KPI 2.2 - Crecimiento de datos por hora de inserción'
\echo 'Mide cuántos registros se han insertado en RDS por hora.'
SELECT
    date_trunc('hour', inserted_at) AS ingestion_hour,
    COUNT(*) AS records_ingested
FROM "MarineTraffic".position_report
GROUP BY date_trunc('hour', inserted_at)
ORDER BY ingestion_hour DESC
LIMIT 24;

\echo ''
\echo 'KPI 2.3 - Latencia aproximada de ingesta'
\echo 'Diferencia entre el tiempo del mensaje AIS y el momento de inserción en RDS.'
SELECT
    ROUND(AVG(EXTRACT(EPOCH FROM (inserted_at - time_utc)))::numeric, 2) AS avg_ingestion_delay_seconds,
    ROUND(MIN(EXTRACT(EPOCH FROM (inserted_at - time_utc)))::numeric, 2) AS min_ingestion_delay_seconds,
    ROUND(MAX(EXTRACT(EPOCH FROM (inserted_at - time_utc)))::numeric, 2) AS max_ingestion_delay_seconds
FROM "MarineTraffic".position_report
WHERE inserted_at IS NOT NULL
  AND time_utc IS NOT NULL;

\echo ''
\echo 'KPI 2.4 - Consulta crítica con EXPLAIN ANALYZE'
\echo 'Mide tiempo de ejecución de una consulta KPI crítica.'
EXPLAIN ANALYZE
SELECT
    hour,
    total_messages,
    active_vessels,
    avg_speed
FROM "MarineTraffic".kpi_hourly_traffic
ORDER BY hour DESC
LIMIT 10;


\echo ''
\echo '3. KPIs de calidad y fiabilidad de los datos'
\echo '------------------------------------------------------------'

\echo ''
\echo 'KPI 3.1 - Distribución de calidad de datos'
\echo 'Clasifica los registros como válidos o con posibles inconsistencias.'
SELECT
    quality_status,
    COUNT(*) AS records,
    ROUND(
        100.0 * COUNT(*) / NULLIF(SUM(COUNT(*)) OVER (), 0),
        2
    ) AS percentage
FROM "MarineTraffic".position_quality_check
GROUP BY quality_status
ORDER BY records DESC;

\echo ''
\echo 'KPI 3.2 - Porcentaje global de registros inconsistentes'
\echo 'Número de entradas no válidas dividido entre el total de entradas analizadas.'
SELECT
    COUNT(*) AS total_records,
    COALESCE(SUM(CASE WHEN quality_status <> 'valid' THEN 1 ELSE 0 END), 0) AS inconsistent_records,
    ROUND(
        100.0 * COALESCE(SUM(CASE WHEN quality_status <> 'valid' THEN 1 ELSE 0 END), 0)
        / NULLIF(COUNT(*), 0),
        2
    ) AS inconsistent_records_percentage
FROM "MarineTraffic".position_quality_check;

\echo ''
\echo 'KPI 3.3 - Validación de coordenadas y velocidades extremas'
\echo 'Permite identificar registros potencialmente problemáticos para revisión.'
SELECT
    id,
    mmsi,
    ship_name,
    latitude,
    longitude,
    sog,
    quality_status,
    time_utc
FROM "MarineTraffic".position_quality_check
WHERE quality_status <> 'valid'
ORDER BY time_utc DESC
LIMIT 20;

\echo ''
\echo 'KPI 3.4 - Disponibilidad lógica del pipeline'
\echo 'Evalúa cuándo se insertó el último registro y si hay datos recientes.'
SELECT
    MAX(inserted_at) AS last_record_inserted_at,
    NOW() - MAX(inserted_at) AS time_since_last_record,
    CASE
        WHEN MAX(inserted_at) IS NULL THEN 'no_data_yet'
        WHEN NOW() - MAX(inserted_at) <= INTERVAL '15 minutes' THEN 'recent_data'
        WHEN NOW() - MAX(inserted_at) <= INTERVAL '1 hour' THEN 'delayed_data'
        ELSE 'no_recent_data'
    END AS logical_pipeline_status
FROM "MarineTraffic".position_report;

\echo ''
\echo 'KPI 3.5 - Nota sobre tasa de error de ingesta'
\echo 'Los errores de inserción se controlan en Python mediante try/except y rollback.'
SELECT
    'La tasa real de error de ingesta debe calcularse combinando registros recibidos, inserciones correctas y errores registrados en logs/CloudWatch.' AS ingestion_error_rate_note;


\echo ''
\echo '4. KPIs de impacto y adopción'
\echo '------------------------------------------------------------'

\echo ''
\echo 'KPI 4.1 - Indicadores funcionales disponibles'
\echo 'Número de vistas analíticas creadas para alimentar informes o dashboards.'
SELECT
    COUNT(*) AS analytical_views_available
FROM information_schema.views
WHERE table_schema = 'MarineTraffic'
  AND table_name IN (
      'position_report_enriched',
      'position_quality_check',
      'kpi_hourly_traffic',
      'kpi_ship_type_distribution'
  );

\echo ''
\echo 'KPI 4.2 - Barcos activos detectados'
\echo 'Indicador funcional principal para monitorización marítima.'
SELECT
    COUNT(DISTINCT mmsi) AS active_vessels
FROM "MarineTraffic".position_report;

\echo ''
\echo 'KPI 4.3 - Velocidad media de embarcaciones'
\echo 'Indicador descriptivo de la actividad marítima registrada.'
SELECT
    ROUND(AVG(sog)::numeric, 2) AS avg_speed
FROM "MarineTraffic".position_report
WHERE sog IS NOT NULL;

\echo ''
\echo 'KPI 4.4 - Distribución por estado de movimiento'
\echo 'Clasifica la actividad de los barcos según su velocidad.'
SELECT
    movement_status,
    COUNT(*) AS total_messages,
    COUNT(DISTINCT mmsi) AS vessels
FROM "MarineTraffic".position_report_enriched
GROUP BY movement_status
ORDER BY total_messages DESC;

\echo ''
\echo 'KPI 4.5 - Top 10 barcos con más posiciones registradas'
\echo 'Permite identificar embarcaciones con mayor presencia en la zona monitorizada.'
SELECT
    mmsi,
    MAX(ship_name) AS ship_name,
    COUNT(*) AS position_messages,
    ROUND(AVG(sog)::numeric, 2) AS avg_speed
FROM "MarineTraffic".position_report
GROUP BY mmsi
ORDER BY position_messages DESC
LIMIT 10;

\echo ''
\echo 'KPI 4.6 - Distribución por tipo de barco'
\echo 'Permite analizar qué tipos de embarcaciones aparecen en el sistema.'
SELECT
    ship_type,
    vessels,
    position_messages,
    avg_speed
FROM "MarineTraffic".kpi_ship_type_distribution
ORDER BY vessels DESC;

\echo ''
\echo 'KPI 4.7 - Precisión de modelo predictivo'
\echo 'No aplica en la fase actual porque no se ha implementado un modelo ML.'
SELECT
    'not_applicable' AS model_metric_status,
    'No predictive model has been implemented in the current phase. This KPI is proposed as future work.' AS explanation;

\echo ''
\echo '============================================================'
\echo 'FIN DE CONSULTAS KPI'
\echo '============================================================'
