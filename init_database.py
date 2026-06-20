#!/usr/bin/env python3
"""Initialize the database schema on startup."""

import os
import psycopg2
import sys

def init_db():
    """Create database tables if they don't exist."""
    try:
        conn = psycopg2.connect(
            host=os.getenv("PGHOST", "postgres"),
            port=int(os.getenv("PGPORT", "5432")),
            user=os.getenv("PGUSER", "postgres"),
            password=os.getenv("PGPASSWORD", ""),
            database=os.getenv("PGDATABASE", "railway")
        )
        
        cur = conn.cursor()
        
        # Create sensor_readings table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sensor_readings (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                channel VARCHAR(50) NOT NULL,
                value FLOAT NOT NULL,
                is_anomaly BOOLEAN DEFAULT FALSE
            )
        """)
        
        # Create anomaly_alerts table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS anomaly_alerts (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                channel VARCHAR(50) NOT NULL,
                value FLOAT NOT NULL,
                unit VARCHAR(20) NOT NULL,
                is_anomaly BOOLEAN DEFAULT TRUE
            )
        """)
        
        # Create indexes
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sensor_readings_channel ON sensor_readings(channel)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sensor_readings_timestamp ON sensor_readings(timestamp)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_anomaly_alerts_timestamp ON anomaly_alerts(timestamp)")
        
        conn.commit()
        cur.close()
        conn.close()
        
        print("✓ Database initialized successfully")
        return True
        
    except Exception as e:
        print(f"✗ Database initialization failed: {str(e)}", file=sys.stderr)
        return False

if __name__ == "__main__":
    success = init_db()
    sys.exit(0 if success else 1)

