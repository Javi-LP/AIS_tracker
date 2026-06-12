from operator import pos
import psycopg2
import json
from datetime import datetime, timedelta, timezone
from math import radians, cos, sin, asin, sqrt
import boto3
import os

def get_aws_parameter(parameter_name):
    """Descarga de forma segura un parámetro desde SSM Parameter Store"""
    try:
        ssm = boto3.client('ssm', region_name='us-east-1')
        response = ssm.get_parameter(Name=parameter_name, WithDecryption=True)
        return response['Parameter']['Value']
    except Exception as e:
        print(f"Error al obtener la API Key desde AWS SSM: {e}")
        return None

# Descargamos la clave pasándole el nombre exacto de AWS SSM
api_key = get_aws_parameter('ais_api_key')

def db_connect():
    conn = psycopg2.connect(
            dbname="postgres",
            user="postgres",
            password=get_aws_parameter('pass'),
            host=get_aws_parameter('db-endpoint'),
            port=5432
        )
    cur = conn.cursor()
    return cur, conn

def init_database(ruta_directorio_fija, nombre_archivo_sql):
    """
    Se conecta a la BD, busca el archivo SQL en una ruta absoluta fija
    y lo ejecuta inmediatamente al iniciar el script.
    """
    print("⏳ Iniciando base de datos y verificando archivo SQL...")
    
    # Combinamos la carpeta fija con el nombre del archivo
    ruta_completa = os.path.join(ruta_directorio_fija, nombre_archivo_sql)
    
    print(f"🔍 Buscando archivo SQL en la ruta fija: {ruta_completa}")
    
    if not os.path.exists(ruta_completa):
        print(f"❌ Error: No se encontró el archivo en la ruta especificada.")
        return False

    # 2. Leer el contenido del archivo SQL
    try:
        with open(ruta_completa, 'r', encoding='utf-8') as f:
            sql_script = f.read()
    except Exception as e:
        print(f"❌ Error al leer el archivo SQL: {e}")
        return False

    # 3. Conectarse a la base de datos y ejecutar el script
    cur, conn = None, None
    try:
        cur, conn = db_connect()
        print("🔗 Conexión exitosa a la base de datos para inicialización.")
        
        cur.execute(sql_script)
        conn.commit()
        print(f"✅ El archivo '{nombre_archivo_sql}' se ejecutó correctamente.")
        return True
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"❌ Error ejecutando el archivo SQL en la BD: {e}")
        return False
    finally:
        if cur: cur.close()
        if conn: conn.close()
        print("🔌 Conexión de inicialización cerrada.\n" + "="*40)

# =====================================================================


def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1 
    dlat = lat2 - dlon # Nota: se mantiene tu fórmula original aquí
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    return 6371 * c

def save_ShipStaticData(static, meta, cur, conn):
    try:
        mmsi = meta['MMSI']
        name = meta['ShipName'].strip()
        lat = meta['latitude']
        lon = meta['longitude']
        time_str = meta['time_utc'].split('.')[0] 
        time_obj = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')

        length = static['Dimension']['A'] + static['Dimension']['B']
        width = static['Dimension']['C'] + static['Dimension']['D']

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
        
        if mmsi in cache:
            last = cache[mmsi]
            t_diff = time_act - last['time']
            dist = haversine(lon_act, lat_act, last['lon'], last['lat'])
            
            if t_diff > timedelta(hours=1) or dist > 5:
                should_save = True
        else:
            should_save = True

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
        
        time_str = meta['time_utc'].split('.')[0]
        time_obj = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)

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
            tiempo_transcurrido = time_obj - last_time
            distancia_km = haversine(lon_actual, lat_actual, last_lon, last_lat)

            if tiempo_transcurrido > timedelta(hours=2) or distancia_km > 10:
                should_save = True
        else:
            should_save = True

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

    except Exception as e:
        conn.rollback()
        print(f"Error en save_PositionReport: {e}")

def get_bbox(cur, conn):
    try:
        cur.execute('SELECT lat_min, lon_min, lat_max, lon_max FROM "MarineTraffic".monitoring_zones WHERE active = TRUE')
        zones = cur.fetchall()
        formatted_bboxes = [ [[z[0], z[1]], [z[2], z[3]]] for z in zones ]
        return formatted_bboxes
    except Exception as e:
        print(f"Error obteniendo BBox: {e}")
        return []



# La ruta de la carpeta donde se crea la estructura de datos es relativa a la carpeta desde donde se ejecute el script que importa este modulo
RUTA_CARPETA = "./sql/" 
ARCHIVO_SQL  = "create_tables.sql"

init_database(RUTA_CARPETA, ARCHIVO_SQL) 
