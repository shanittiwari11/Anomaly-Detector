-- Create sensor_readings table
CREATE TABLE IF NOT EXISTS sensor_readings (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    channel VARCHAR(50) NOT NULL,
    value FLOAT NOT NULL,
    is_anomaly BOOLEAN DEFAULT FALSE
);

-- Create anomaly_alerts table
CREATE TABLE IF NOT EXISTS anomaly_alerts (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    channel VARCHAR(50) NOT NULL,
    value FLOAT NOT NULL,
    unit VARCHAR(20) NOT NULL,
    is_anomaly BOOLEAN DEFAULT TRUE
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_sensor_readings_channel ON sensor_readings(channel);
CREATE INDEX IF NOT EXISTS idx_sensor_readings_timestamp ON sensor_readings(timestamp);
CREATE INDEX IF NOT EXISTS idx_anomaly_alerts_timestamp ON anomaly_alerts(timestamp);

