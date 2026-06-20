#!/usr/bin/env python3
"""
Simple sensor data producer that writes directly to PostgreSQL.
No Kafka dependency.
"""

import os
import random
import time
import uuid
import logging
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import execute_values

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

DB_HOST = os.getenv("PGHOST", "postgres")
DB_PORT = int(os.getenv("PGPORT", "5432"))
DB_USER = os.getenv("PGUSER", "postgres")
DB_PASSWORD = os.getenv("PGPASSWORD", "")
DB_NAME = os.getenv("PGDATABASE", "railway")

EMIT_INTERVAL = float(os.getenv("EMIT_INTERVAL_SECONDS", "1"))
ANOMALY_PROBABILITY = float(os.getenv("ANOMALY_PROBABILITY", "0.15"))
SENSOR_ID = os.getenv("SENSOR_ID", f"sensor-{uuid.uuid4().hex[:6]}")

CHANNELS = {
    "temperature": (70.0, 5.0, "°C"),
    "vibration": (12.0, 2.0, "mm/s"),
    "pressure": (101.3, 0.8, "kPa"),
}

drift_state = {ch: {"active": False, "steps": 0, "max_steps": 0, "offset": 0.0} for ch in CHANNELS}

def _generate_reading(channel: str):
    mean, std, _ = CHANNELS[channel]
    ds = drift_state[channel]
    base = random.gauss(mean, std)
    is_anomaly = False

    if ds["active"]:
        ds["steps"] += 1
        ds["offset"] += random.uniform(1.5, 3.0)
        base += ds["offset"]
        is_anomaly = True
        if ds["steps"] >= ds["max_steps"]:
            ds["active"] = False
            ds["offset"] = 0.0
        return round(base, 3), is_anomaly

    if random.random() < ANOMALY_PROBABILITY:
        anomaly_type = random.choice(["spike", "drift"])
        if anomaly_type == "spike":
            base += random.uniform(mean * 0.5, mean * 1.2)
            is_anomaly = True
        else:
            ds["active"] = True
            ds["steps"] = 0
            ds["max_steps"] = random.randint(5, 15)
            ds["offset"] = 0.0
            ds["offset"] += random.uniform(1.5, 3.0)
            base += ds["offset"]
            is_anomaly = True

    return round(base, 3), is_anomaly

def build_message():
    readings = {}
    anomaly_channels = []

    for channel in CHANNELS:
        value, is_anomaly = _generate_reading(channel)
        _, _, unit = CHANNELS[channel]
        readings[channel] = {"value": value, "unit": unit}
        if is_anomaly:
            anomaly_channels.append(channel)

    return {
        "sensor_id": SENSOR_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "readings": readings,
        "anomaly_channels": anomaly_channels,
        "message_id": str(uuid.uuid4()),
    }

def write_to_db(msg):
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            connect_timeout=5
        )
        cur = conn.cursor()
        sensor_id = msg["sensor_id"]
        timestamp = msg["timestamp"]
        readings = msg["readings"]
        anomaly_chs = set(msg.get("anomaly_channels", []))

        rows = []
        for channel, data in readings.items():
            value = data["value"]
            unit = data["unit"]
            is_anomaly = channel in anomaly_chs
            rows.append((sensor_id, timestamp, channel, value, unit, is_anomaly))

        if rows:
            execute_values(
                cur,
                "INSERT INTO sensor_readings (sensor_id, timestamp, channel, value, unit, is_anomaly) VALUES %s",
                rows
            )
            conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"DB write error: {e}")
        return False

def run():
    logger.info("🚀 Starting producer  sensor_id=%s  interval=%.1fs", SENSOR_ID, EMIT_INTERVAL)
    sent = 0
    try:
        while True:
            msg = build_message()
            if write_to_db(msg):
                sent += 1
                if sent % 60 == 0:
                    logger.info("📤 Sent %d messages  |  last anomalies: %s", sent, msg["anomaly_channels"] or "none")
            time.sleep(EMIT_INTERVAL)
    except KeyboardInterrupt:
        logger.info("Producer stopped. Total messages sent: %d", sent)

if __name__ == "__main__":
    run()

