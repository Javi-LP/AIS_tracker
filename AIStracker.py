import asyncio
import websockets
import json
from datetime import datetime, timezone
import DBUtils.DBManager as db_manager
import boto3

def get_aws_parameter(parameter_name):
    """Descarga de forma segura un parámetro desde SSM Parameter Store"""
    try:
        # Inicializa el cliente de Systems Manager indicando tu región (ej. us-east-1)
        ssm = boto3.client('ssm', region_name='us-east-1')
        
        # Solicita el parámetro a AWS
        response = ssm.get_parameter(Name=parameter_name, WithDecryption=True)
        return response['Parameter']['Value']
    except Exception as e:
        print(f"Error al obtener la API Key desde AWS SSM: {e}")
        return None

# Descargamos la clave pasándole el nombre exacto de AWS SSM
api_key = get_aws_parameter('ais_api_key')

pos_cache = {}

async def connect_ais_stream(cur, conn):
    loop = asyncio.get_event_loop()
    
    # 1. CARGA INICIAL DE CACHÉ (Se hace una sola vez al arrancar)
    print("Cargando caché de posiciones desde PostgreSQL...")
    try:
        cur.execute("""
            SELECT DISTINCT ON (mmsi) mmsi, time_utc, latitude, longitude 
            FROM "MarineTraffic".position_report 
            ORDER BY mmsi, time_utc DESC
        """)
        for r in cur.fetchall():
            # r[0]=mmsi, r[1]=time, r[2]=lat, r[3]=lon
            pos_cache[r[0]] = {'time': r[1], 'lat': r[2], 'lon': r[3]}
        print(f"Caché lista con {len(pos_cache)} barcos.")
    except Exception as e:
        print(f"No se pudo cargar la caché inicial: {e}")

    # 2. BUCLE PRINCIPAL DE CONEXIÓN
    while True:
        try:
            bboxes = db_manager.get_bbox(cur, conn)
            if not bboxes:
                print("⚠️ No hay zonas activas. Reintentando en 10s...")
                await asyncio.sleep(10)
                continue

            print(f"📡 Conectando a AISStream para {len(bboxes)} zonas...")
            
            async with websockets.connect(
                "wss://stream.aisstream.io/v0/stream",
                ping_interval=20, 
                ping_timeout=20
            ) as websocket:

                subscribe_message = {"APIKey": api_key, "BoundingBoxes": bboxes}
                await websocket.send(json.dumps(subscribe_message))

                async for message_json in websocket:
                    message = json.loads(message_json)
                    msg_type = message.get("MessageType")
                    meta = message.get("MetaData")

                    if msg_type == "ShipStaticData":
                        # Guardado estático en hilo separado
                        loop.run_in_executor(None, db_manager.save_ShipStaticData, 
                                             message['Message']['ShipStaticData'], meta, cur, conn)
                        
                    elif msg_type == "PositionReport":
                        # Guardado de posición con filtro de caché en hilo separado
                        # Usamos la función optimizada para no saturar con SELECTs
                        loop.run_in_executor(None, db_manager.save_PositionReport_with_cache, 
                                             message['Message']['PositionReport'], meta, cur, conn, pos_cache)

        except (websockets.ConnectionClosed, websockets.InvalidState, Exception) as e:
            print(f"Conexión perdida o error: {e}. Reconectando en 5 segundos...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        cur, conn = db_manager.db_connect()  # Verificar conexión a la base de datos antes de iniciar el stream
        asyncio.run(connect_ais_stream(cur, conn))
    except KeyboardInterrupt:
        cur.close()
        conn.close()
