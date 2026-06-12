from operator import pos
import psycopg2
import json
from datetime import datetime, timedelta, timezone
from math import radians, cos, sin, asin, sqrt

def db_connect():
    conn = psycopg2.connect(
            dbname="marinetraffic",
            user="postgres",
            host="marinetraffic-db.cmo6j2lbjulb.us-east-1.rds.amazonaws.com",
            port=5432
        )
    cur = conn.cursor()
    return cur, conn

def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    return 6371 * c

def save_ShipStaticData(static, meta, cur, conn):
    try:
        
        # 2. Extracción y Limpieza de datos
        # Nota: La API a veces trae espacios en blanco en el nombre        
        mmsi = meta['MMSI']
        name = meta['ShipName'].strip()
        lat = meta['latitude']
        lon = meta['longitude']
        # Convertimos el string de tiempo de Go/AISStream a datetime de Python
        time_str = meta['time_utc'].split('.')[0] 
        time_obj = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')

        # Cálculos de dimensiones
        length = static['Dimension']['A'] + static['Dimension']['B']
        width = static['Dimension']['C'] + static['Dimension']['D']

        # 3. Query de inserción
        insert_query = """
        INSERT INTO "MarineTraffic".ais_ship_static_data 
        (callsign, mmsi, ship_name, ship_type, draught, length, width)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        
        cur.execute(insert_query, (
            static['CallSign'],
            mmsi, 
            name, 
            static['Type'], 
            static['MaximumStaticDraught'],
            length,
            width,
            #json.dumps(message) # Guardamos el JSON completo en la columna JSONB
        ))

        conn.commit()
        print(f"Guardado Static Data: {name} ({mmsi})")

    except Exception as e:
        conn.rollback()
        print(f"Error en save_ShipStaticData: {e}")

def save_PositionReport_with_cache(ais, meta, cur, conn, cache):
    try:
        mmsi = meta['MMSI']
        lat_act = ais['Latitude']
        lon_act = ais['Longitude']
        time_str = meta['time_utc'].split('.')[0]
        time_act = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)

        should_save = False
        
        # 1. VERIFICAR EN CACHÉ (No hay SELECT!)
        if mmsi in cache:
            last = cache[mmsi]
            t_diff = time_act - last['time']
            dist = haversine(lon_act, lat_act, last['lon'], last['lat'])
            
            if t_diff > timedelta(hours=1) or dist > 5:
                should_save = True
        else:
            should_save = True

        # 2. GUARDAR E ACTUALIZAR CACHÉ
        if should_save:
            insert_query = """
                INSERT INTO "MarineTraffic".position_report 
                (mmsi, ship_name, latitude, longitude, sog, cog, nav_status, time_utc)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            cur.execute(insert_query, (
                mmsi, meta['ShipName'].strip(), lat_act, lon_act,
                ais['Sog'], ais['Cog'], ais['NavigationalStatus'], time_act
            ))
            conn.commit()
            
            # Actualizamos la memoria para la próxima vez
            cache[mmsi] = {'time': time_act, 'lat': lat_act, 'lon': lon_act}
            print(f"🚀 [DB + CACHE] Guardado: {meta['ShipName']}")

    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")

def save_PositionReport(ais, meta, cur, conn):
    try:

        mmsi = meta['MMSI']
        name = meta['ShipName'].strip()
        lat_actual = ais['Latitude']
        lon_actual = ais['Longitude']
        
        # Limpieza de tiempo
        time_str = meta['time_utc'].split('.')[0]
        time_obj = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)

        # 1. BUSCAR LA ÚLTIMA POSICIÓN CONOCIDA DE ESTE MMSI
        check_query = """
            SELECT time_utc, latitude, longitude 
            FROM "MarineTraffic".position_report 
            WHERE mmsi = %s 
            ORDER BY time_utc DESC 
            LIMIT 1
        """
        cur.execute(check_query, (mmsi,))
        last_record = cur.fetchone()

        should_save = False

        if last_record:
            last_time, last_lat, last_lon = last_record
            
            # Cálculo de tiempo transcurrido
            tiempo_transcurrido = time_obj - last_time
            
            # Cálculo de distancia aproximada (Fórmula simplificada de Haversine en Python)
            # Para mayor precisión podrías usar geopy.distance
            from math import radians, cos, sin, asin, sqrt
            def haversine(lon1, lat1, lon2, lat2):
                lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
                dlon = lon2 - lon1 
                dlat = lat2 - lat1 
                a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
                c = 2 * asin(sqrt(a)) 
                return 6371 * c # Radio de la Tierra en km

            distancia_km = haversine(lon_actual, lat_actual, last_lon, last_lat)

            # Lógica de filtrado: Mas de 2 horas O mas de 10 km
            if tiempo_transcurrido > timedelta(hours=2) or distancia_km > 10:
                should_save = True
        else:
            # Si es la primera vez que vemos este barco, guardamos siempre
            should_save = True

        # 2. INSERCIÓN SI CUMPLE LOS REQUISITOS
        if should_save:
            insert_query = """
                INSERT INTO "MarineTraffic".position_report 
                (mmsi, ship_name, latitude, longitude, sog, cog, nav_status, time_utc)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            cur.execute(insert_query, (
                mmsi, name, lat_actual, lon_actual,
                ais['Sog'], ais['Cog'], ais['NavigationalStatus'], time_obj
            ))
            conn.commit()
            print(f"Guardado Position report: {name} ({mmsi})")
        else:
            pass

    except Exception as e:
        conn.rollback()
        print(f"Error en save_PositionReport: {e}")

def get_bbox(cur, conn):
    try:
        # Solo traemos las zonas activas
        cur.execute('SELECT lat_min, lon_min, lat_max, lon_max FROM "MarineTraffic".monitoring_zones WHERE active = TRUE')
        zones = cur.fetchall()
        
        # Formateamos para AisStream: [[ [latS, lonO], [latN, lonE] ], ...]
        formatted_bboxes = [ [[z[0], z[1]], [z[2], z[3]]] for z in zones ]
        return formatted_bboxes
        
    except Exception as e:
        print(f"Error obteniendo BBox: {e}")
        return []
