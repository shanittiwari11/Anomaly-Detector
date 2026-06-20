"""
train_models.py
---------------
Offline training script. Generates synthetic historical data,
trains both detectors, and saves models to models/saved/.

Usage:
    python scripts/train_models.py [--model isolation_forest|lstm|both]
                                   [--samples 5000]
"""

import argparse
import logging
import os
import sys
import random

import numpy as np

# Ensure project root is on path when running from scripts/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

os.makedirs("models/saved", exist_ok=True)


def generate_historical(n: int = 5000, anomaly_fraction: float = 0.0) -> list[float]:
    """
    Generate normal-only data for model training.
    anomaly_fraction = 0 means clean baseline.
    """
    vals = [random.gauss(70, 5) for _ in range(n)]
    if anomaly_fraction > 0:
        for i in random.sample(range(n), int(n * anomaly_fraction)):
            vals[i] += random.uniform(30, 70)
    return vals


def train_isolation_forest(samples: int):
    from models.isolation_forest import IsolationForestDetector
    detector = IsolationForestDetector()
    data = generate_historical(samples)
    logger.info("Training IsolationForest on %d normal samples…", samples)
    detector.fit(data)
    logger.info("✅ IsolationForest saved.")


def train_lstm(samples: int):
    from models.lstm_autoencoder import LSTMAutoencoderDetector
    detector = LSTMAutoencoderDetector()
    data = generate_historical(samples)
    logger.info("Training LSTM Autoencoder on %d normal samples…", samples)
    detector.fit(data)
    logger.info("✅ LSTM Autoencoder saved.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model",   choices=["isolation_forest", "lstm", "both"],
                        default="both")
    parser.add_argument("--samples", type=int, default=5000)
    args = parser.parse_args()

    if args.model in ("isolation_forest", "both"):
        train_isolation_forest(args.samples)

    if args.model in ("lstm", "both"):
        train_lstm(args.samples)

    logger.info("All requested models trained. Files in models/saved/")


if __name__ == "__main__":
    main()
