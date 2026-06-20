import os
import time
import random
import psycopg2
from datetime import datetime
import sys

# Try to parse DATABASE_URL first (Railway auto-provides this)
database_url = os.getenv("DATABASE_URL")

if database_url:
    # Parse DATABASE_URL format: postgresql://user:password@host:port/database
    import urllib.parse
    parsed = urllib.parse.urlparse(database_url)
    DB_HOST = parsed.hostname
    DB_PORT = parsed.port or 5432
    DB_USER = parsed.username
    DB_PASSWORD = parsed.password
    DB_NAME = parsed.path.lstrip('/')
else:
    # Fallback to individual env vars
    DB_HOST = os.getenv("PGHOST", "localhost")
    DB_PORT = int(os.getenv("PGPORT", "5432"))
    DB_USER = os.getenv("PGUSER", "postgres")
    DB_PASSWORD = os.getenv("PGPASSWORD", "")
    DB_NAME = os.getenv("PGDATABASE", "railway")

print(f"[Producer] Connecting to {DB_HOST}:{DB_PORT}/{DB_NAME}", flush=True)
print(f"[Producer] User: {DB_USER}", flush=True)

def get_db():
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            connect_timeout=10
        )
        print("[Producer] ✓ Database connected", flush=True)
        return conn
    except Exception as e:
        print(f"[Producer] ✗ Connection error: {e}", flush=True)
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
        print(f"[Producer] Error initializing tables: {e}", flush=True)

def generate_sensor_data():
    """Generate and insert sensor data."""
    sensor_id = "sensor-001"
    channels = ["temperature", "vibration", "pressure"]
    insert_count = 0
    
    while True:
        try:
            conn = get_db()
            cur = conn.cursor()
            
            for channel in channels:
                # Generate realistic data
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
                    (sensor_id, channel, value, False)
                )
            
            conn.commit()
            insert_count += 3
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✓ Inserted 3 readings (total: {insert_count})", flush=True)
            cur.close()
            conn.close()
            
            time.sleep(1)
        
        except Exception as e:
            print(f"[Producer] Insert error: {e}", flush=True)
            try:
                cur.close()
                conn.close()
            except:
                pass
            time.sleep(5)

if __name__ == "__main__":
    print("[Producer] Starting sensor data producer...", flush=True)
    
    try:
        init_tables()
        print("[Producer] Beginning data generation...", flush=True)
        generate_sensor_data()
    except KeyboardInterrupt:
        print("[Producer] Stopped by user", flush=True)
    except Exception as e:
        print(f"[Producer] Fatal error: {e}", flush=True)
