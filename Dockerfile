FROM python:3.11-slim

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc && rm -rf /var/lib/apt/lists/*

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    kafka-python==2.0.2 \
    streamlit==1.33.0 \
    pandas==2.2.2 \
    numpy==1.26.4 \
    plotly==5.22.0 \
    python-dotenv==1.0.1 \
    psycopg2-binary==2.9.9

# Copy all application code
COPY dashboard/ ./dashboard/
COPY consumer/ ./consumer/
COPY producer/ ./producer/
COPY models/ ./models/

ENV PYTHONUNBUFFERED=1

EXPOSE 8501

CMD ["streamlit", "run", "dashboard/app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
