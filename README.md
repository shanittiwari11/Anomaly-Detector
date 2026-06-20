# Anomaly Detection System : https://anomaly-detector-production.up.railway.app/

I made a real time anomaly detection system using Apache Kafka, machine learning models, and a Streamlit dashboard to monitor sensor readings and identify anomalies.

## Features

- Real time Data Processing: Kafka based streaming pipeline for sensor data
- Multiple Detection Models: Isolation Forest and LSTM Autoencoder detectors
- Live Dashboard: Streamlit web interface with interactive visualizations
- PostgreSQL Storage: Persistent storage for sensor readings and alerts
- Mult channel Monitoring: Temperature, vibration, and pressure sensors
- Docker Compose: Easy deployment with containerized services

## Architecture

```
sensor-producer (Kafka) → anomaly-consumer (ML models) → anomaly-alerts
                              ↓
                         PostgreSQL
                              ↑
                        streamlit-dashboard
```

## Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for local development)
- Git

## Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/shanittiwari11/Anomaly-Detector.git
   cd Anomaly-Detector
   ```

2. **Start all services**
   ```bash
   docker compose up -d
   ```

3. **Access the dashboard**
   Open your browser and navigate to: `http://localhost:8501`

4. **Other services**
   - Kafka UI: `http://localhost:8080`
   - PostgreSQL: `localhost:5432`

## Services

| Service | Port | Description |
|---------|------|-------------|
| streamlit-dashboard | 8501 | Real-time anomaly detection monitor |
| kafka | 9092 | Kafka broker |
| zookeeper | 2181 | Kafka coordination |
| postgres | 5432 | Data storage |
| kafka-ui | 8080 | Kafka management UI |

## Environment Variables

Configure in `docker-compose.yml`:

```yaml
KAFKA_BOOTSTRAP_SERVERS: kafka:29092
DB_HOST: postgres
DB_PORT: 5432
DB_USER: anomaly_user
DB_PASSWORD: anomaly_pass
DB_NAME: anomaly_db
MODEL_TYPE: isolation_forest  # or lstm
ANOMALY_PROBABILITY: 0.05
EMIT_INTERVAL_SECONDS: 1
```

## Project Structure

```
├── consumer/                 # Kafka consumer & anomaly detection
│   └── kafka_consumer.py
├── dashboard/               # Streamlit web interface
│   └── app.py
├── producer/               # Sensor data simulator
│   └── sensor_simulator.py
├── models/                 # ML detection models
│   ├── isolation_forest.py
│   ├── lstm_autoencoder.py
│   └── saved/
├── docker-compose.yml
├── Dockerfile.consumer
├── Dockerfile.dashboard
├── Dockerfile.producer
└── requirements.txt
```

## Development

### Local Setup

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Running Services Locally

```bash
# Producer
python producer/sensor_simulator.py

# Consumer
python consumer/kafka_consumer.py

# Dashboard
streamlit run dashboard/app.py
```

## Model Performance

- Isolation Forest: Fast, lightweight, handles multivariate data
- LSTM Autoencoder: Deep learning approach, detects temporal anomalies

## Database Schema

### sensor_readings
- sensor_id
- timestamp
- channel (temperature, vibration, pressure)
- value
- is_anomaly
- anomaly_score

### anomaly_alerts
- sensor_id
- timestamp
- channel
- value
- is_anomaly
- score
- method

## Deployment

### Docker Hub
```bash
docker build -t username/anomaly-detection -f Dockerfile.dashboard .
docker push username/anomaly-detection
```

### Kubernetes
```bash
kubectl apply -f k8s-deployment.yaml
```

### Cloud Platforms
- **Railway**: Connect GitHub repo and deploy
- **Render**: Deploy Docker Compose directly
- **AWS ECS**: Push to ECR and deploy
- **Google Cloud Run**: Containerize and deploy

## Troubleshooting

### Dashboard not loading
```bash
docker logs streamlit-dashboard
```

### Consumer crashing
```bash
docker logs anomaly-consumer
```

### Kafka connection issues
```bash
docker logs kafka
```

### Reset database
```bash
docker compose down -v
docker compose up -d
```

## License

MIT License

## Author
Shanit Tiwari
