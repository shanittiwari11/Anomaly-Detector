import os
import time
import random
import psycopg2
from datetime import datetime

# Database connection
DB_HOST = os.getenv("PGHOST", "postgres")
DB_PORT = int(os.getenv("PGPORT", "5432"))
DB_USER = os.getenv("PGUSER", "postgres")
DB_PASSWORD = os.getenv("PGPASSWORD", "")
DB_NAME = os.getenv("PGDATABASE", "railway")

def get_db():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )

def init_tables():
    """Create tables if they don't exist."""
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
    print("✓ Tables initialized")

def generate_sensor_data():
    """Generate and insert sensor data."""
    try:
        conn = get_db()
        cur = conn.cursor()
        
        sensor_id = "sensor-001"
        channels = ["temperature", "vibration", "pressure"]
        
        while True:
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
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Inserted data for {sensor_id}")
            time.sleep(1)
    
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(5)
    finally:
        if conn:
            cur.close()
            conn.close()

if __name__ == "__main__":
    print("Starting sensor data producer...")
    print(f"Connecting to {DB_HOST}:{DB_PORT}/{DB_NAME}")
    
    try:
        init_tables()
        generate_sensor_data()
    except KeyboardInterrupt:
        print("\nProducer stopped")
    except Exception as e:
        print(f"Fatal error: {e}")
