import os
import time
import random
import psycopg2
from datetime import datetime

# Railway provides these when a Postgres service is linked
DB_HOST = os.getenv("PGHOST", "postgres")
DB_PORT = int(os.getenv("PGPORT", "5432"))
DB_USER = os.getenv("PGUSER", "postgres")
DB_PASSWORD = os.getenv("PGPASSWORD")
DB_NAME = os.getenv("PGDATABASE", "railway")

print(f"[Producer] Configuration:", flush=True)
print(f"  Host: {DB_HOST}", flush=True)
print(f"  Port: {DB_PORT}", flush=True)
print(f"  Database: {DB_NAME}", flush=True)
print(f"  User: {DB_USER}", flush=True)
print(f"[Producer] Attempting connection...", flush=True)

def get_db():
    try:
        if DB_PASSWORD:
            conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME,
                connect_timeout=10
            )
        else:
            conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                user=DB_USER,
                database=DB_NAME,
                connect_timeout=10
            )
        print("[Producer] ✓ Database connected", flush=True)
        return conn
    except Exception as e:
        print(f"[Producer] ✗ Connection failed: {e}", flush=True)
        raise

def init_tables():
    """Create tables if they don't exist."""
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sensor_readings (
                id SERIAL PRIMARY KEY,
                sensor_id VARCHAR(50),
                timestamp TIMESTAMP DEFAULT NOW(),
                channel VARCHAR(50),
                value FLOAT,
                is_anomaly BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_readings_timestamp ON sensor_readings(timestamp DESC);
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS anomaly_alerts (
                id SERIAL PRIMARY KEY,
                sensor_id VARCHAR(50),
                timestamp TIMESTAMP,
                channel VARCHAR(50),
                value FLOAT,
                unit VARCHAR(20),
                is_anomaly BOOLEAN,
                score FLOAT,
                method VARCHAR(50),
                created_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_alert_timestamp ON anomaly_alerts(timestamp DESC);
        """)
        
        conn.commit()
        cur.close()
        conn.close()
        print("[Producer] ✓ Tables initialized", flush=True)
    except Exception as e:
        print(f"[Producer] Table creation error: {e}", flush=True)

def generate_sensor_data():
    """Generate and insert sensor data with random anomalies."""
    sensor_id = "sensor-001"
    channels = ["temperature", "vibration", "pressure"]
    insert_count = 0
    anomaly_count = 0
    
    while True:
        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()
            
            for channel in channels:
                # 10% chance of anomaly
                is_anomaly = random.random() < 0.10
                
                if is_anomaly:
                    # Generate anomalous data (extreme values)
                    if channel == "temperature":
                        value = random.uniform(80, 150)  # Abnormal temps
                    elif channel == "vibration":
                        value = random.uniform(20, 100)  # High vibration
                    else:  # pressure
                        value = random.uniform(300, 700)  # Extreme pressure
                    anomaly_count += 1
                else:
                    # Generate normal data
                    if channel == "temperature":
                        value = 20 + random.gauss(0, 5)  # Around 20°C
                    elif channel == "vibration":
                        value = 2 + random.gauss(0, 0.5)  # Around 2 mm/s
                    else:  # pressure
                        value = 100 + random.gauss(0, 10)  # Around 100 kPa
                
                # Insert into database
                cur.execute(
                    """INSERT INTO sensor_readings 
                    (sensor_id, channel, value, is_anomaly) 
                    VALUES (%s, %s, %s, %s)""",
                    (sensor_id, channel, value, is_anomaly)
                )
            
            conn.commit()
            insert_count += 3
            
            status = "ANOMALY!" if any([random.random() < 0.10 for _ in range(3)]) else "normal"
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✓ Inserted 3 readings ({status}) | Total: {insert_count} | Anomalies: {anomaly_count}", flush=True)
            cur.close()
            conn.close()
            
            time.sleep(1)
        
        except Exception as e:
            print(f"[Producer] Error: {e}", flush=True)
            if conn:
                try:
                    conn.close()
                except:
                    pass
            print("[Producer] Retrying in 5 seconds...", flush=True)
            time.sleep(5)

if __name__ == "__main__":
    print("[Producer] Starting sensor data producer with random anomalies...", flush=True)
    
    try:
        init_tables()
        print("[Producer] Beginning data generation...", flush=True)
        generate_sensor_data()
    except KeyboardInterrupt:
        print("[Producer] Stopped by user", flush=True)
    except Exception as e:
        print(f"[Producer] Fatal error: {e}", flush=True)
        time.sleep(10)
