import os
import time
import random
import psycopg2
from datetime import datetime
import sys

# Database connection using Railway env vars
DB_HOST = os.getenv("PGHOST", "localhost")
DB_PORT = int(os.getenv("PGPORT", "5432"))
DB_USER = os.getenv("PGUSER", "postgres")
DB_PASSWORD = os.getenv("PGPASSWORD", "")
DB_NAME = os.getenv("PGDATABASE", "railway")

print(f"[Producer] Connecting to {DB_HOST}:{DB_PORT}/{DB_NAME}", file=sys.stderr)
print(f"[Producer] User: {DB_USER}", file=sys.stderr)

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
        print("[Producer] ✓ Database connected", file=sys.stderr)
        return conn
    except Exception as e:
        print(f"[Producer] ✗ Connection error: {e}", file=sys.stderr)
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
        print("[Producer] ✓ Tables initialized", file=sys.stderr)
    except Exception as e:
        print(f"[Producer] Error initializing tables: {e}", file=sys.stderr)
        raise

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
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Inserted 3 readings (total: {insert_count})", file=sys.stderr)
            cur.close()
            conn.close()
            
            time.sleep(1)
        
        except Exception as e:
            print(f"[Producer] Error: {e}", file=sys.stderr)
            time.sleep(5)

if __name__ == "__main__":
    print("[Producer] Starting sensor data producer...", file=sys.stderr)
    
    try:
        init_tables()
        generate_sensor_data()
    except KeyboardInterrupt:
        print("[Producer] Stopped", file=sys.stderr)
    except Exception as e:
        print(f"[Producer] Fatal error: {e}", file=sys.stderr)
