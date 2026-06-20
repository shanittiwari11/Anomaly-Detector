"""
kafka_consumer.py
-----------------
Reads sensor readings from Kafka, runs anomaly detection,
and writes alerts to PostgreSQL.
"""

import json
import logging
import os
import uuid
import time

import psycopg2
from psycopg2.extras import execute_values
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import NoBrokersAvailable

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "sensor-data")
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID", "anomaly-detector-group")
ALERT_TOPIC = os.getenv("ALERT_TOPIC", "sensor-alerts")
MODEL_TYPE = os.getenv("MODEL_TYPE", "isolation_forest").lower()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "anomaly_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "anomaly_pass")
DB_NAME = os.getenv("DB_NAME", "anomaly_db")

def load_model(model_type: str):
    if model_type == "lstm":
        from models.lstm_autoencoder import LSTMAutoencoderDetector
        logger.info("Using LSTM Autoencoder detector")
        return LSTMAutoencoderDetector()
    else:
        from models.isolation_forest import IsolationForestDetector
        logger.info("Using Isolation Forest detector")
        return IsolationForestDetector()

class ChannelDetectorRegistry:
    def __init__(self, model_type: str):
        self.model_type = model_type
        self._detectors = {}

    def get(self, key: str):
        if key not in self._detectors:
            self._detectors[key] = load_model(self.model_type)
            logger.info("Created detector for %s", key)
        return self._detectors[key]

def create_consumer(retries=15, delay=5):
    for attempt in range(1, retries + 1):
        try:
            consumer = KafkaConsumer(
                KAFKA_TOPIC,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                group_id=KAFKA_GROUP_ID,
                auto_offset_reset="latest",
                enable_auto_commit=True,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                consumer_timeout_ms=10000,
            )
            logger.info("✅ Consumer connected to Kafka, topic=%s", KAFKA_TOPIC)
            return consumer
        except NoBrokersAvailable:
            logger.warning("Kafka not ready (attempt %d/%d). Retrying…", attempt, retries)
            time.sleep(delay)
    raise RuntimeError("Could not connect Kafka consumer.")

def create_producer():
    return KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        acks=1,
        retries=3,
    )

def init_db():
    try:
        conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
        cur = conn.cursor()
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
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database init error: {e}")

def write_alert_to_db(alert):
    try:
        conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
        cur = conn.cursor()
        if alert["is_anomaly"]:
            cur.execute(
                "INSERT INTO anomaly_alerts (sensor_id, timestamp, channel, value, unit, is_anomaly, score, method) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (alert["sensor_id"], alert["timestamp"], alert["channel"], alert["value"], alert["unit"], alert["is_anomaly"], alert["score"], alert["method"])
            )
            conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"DB write error: {e}")

def process_message(raw_msg, registry, alert_producer):
    sensor_id = raw_msg.get("sensor_id", "unknown")
    timestamp = raw_msg.get("timestamp", "")
    readings = raw_msg.get("readings", {})
    alerts = []

    for channel, data in readings.items():
        value = data.get("value", 0.0)
        unit = data.get("unit", "")
        key = f"{sensor_id}::{channel}"
        detector = registry.get(key)

        result = detector.update(value)

        alert = {
            "sensor_id": sensor_id,
            "timestamp": timestamp,
            "channel": channel,
            "value": float(value),
            "unit": unit,
            "is_anomaly": bool(result["is_anomaly"]),
            "score": float(result.get("score", 0.0)),
            "method": result.get("method", "unknown"),
            "status": result.get("status", "ok"),
            "message_id": str(uuid.uuid4()),
        }
        alerts.append(alert)

        if result["is_anomaly"]:
            alert_producer.send(ALERT_TOPIC, alert)
            write_alert_to_db(alert)
            logger.warning("🚨 ANOMALY  sensor=%s  channel=%-12s  value=%.2f%s  score=%.4f", sensor_id, channel, value, unit, result.get("score", 0.0))

    return alerts

def run():
    init_db()
    registry = ChannelDetectorRegistry(MODEL_TYPE)
    alert_producer = create_producer()
    consumer = create_consumer()

    processed = 0
    anomalies = 0

    logger.info("🔍 Consumer running  model=%s", MODEL_TYPE)
    try:
        for kafka_msg in consumer:
            raw = kafka_msg.value
            alerts = process_message(raw, registry, alert_producer)
            processed += 1
            anomalies += sum(1 for a in alerts if a["is_anomaly"])

            if processed % 100 == 0:
                logger.info("📊 Processed %d messages  |  total anomalies detected: %d  (%.1f%%)", processed, anomalies, 100 * anomalies / max(processed, 1))
    except KeyboardInterrupt:
        logger.info("Consumer stopped.  processed=%d  anomalies=%d", processed, anomalies)
    finally:
        consumer.close()
        alert_producer.flush()
        alert_producer.close()

if __name__ == "__main__":
    run()
