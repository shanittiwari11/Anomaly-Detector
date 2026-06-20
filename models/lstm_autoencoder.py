"""
lstm_autoencoder.py
-------------------
LSTM-based autoencoder for anomaly detection via reconstruction error.

Architecture:
    Input  → LSTM Encoder (2 layers) → Bottleneck → LSTM Decoder (2 layers) → Dense output

Anomaly criterion:
    reconstruction_error > dynamic_threshold
    where threshold = mean(train_errors) + THRESHOLD_SIGMA * std(train_errors)

Supports:
  - fit(sequences)  — offline training on historical data
  - update(value)   — online inference using a rolling sequence window
  - save / load     — HDF5 weights + JSON config
"""

import os
import json
import logging
import numpy as np
from collections import deque

logger = logging.getLogger(__name__)

SAVED_MODEL_DIR = os.getenv("SAVED_MODEL_DIR", "models/saved")
WEIGHTS_PATH    = os.path.join(SAVED_MODEL_DIR, "lstm_ae_weights.h5")
CONFIG_PATH     = os.path.join(SAVED_MODEL_DIR, "lstm_ae_config.json")

SEQUENCE_LENGTH  = 30      # look-back window
THRESHOLD_SIGMA  = 3.0     # anomaly if error > mean + 3*std
LATENT_DIM       = 32
EPOCHS           = 50
BATCH_SIZE       = 64
LEARNING_RATE    = 1e-3


def _build_model(seq_len: int, n_features: int):
    """Build and return a compiled LSTM autoencoder."""
    # Lazy import — avoids TF import overhead if not needed
    import tensorflow as tf
    from tensorflow.keras import layers, Model, optimizers

    inp = layers.Input(shape=(seq_len, n_features))

    # ── Encoder ──────────────────────────────────────────────
    x = layers.LSTM(64, return_sequences=True)(inp)
    x = layers.Dropout(0.2)(x)
    encoded = layers.LSTM(LATENT_DIM, return_sequences=False)(x)

    # ── Decoder ──────────────────────────────────────────────
    x = layers.RepeatVector(seq_len)(encoded)
    x = layers.LSTM(LATENT_DIM, return_sequences=True)(x)
    x = layers.Dropout(0.2)(x)
    x = layers.LSTM(64, return_sequences=True)(x)
    decoded = layers.TimeDistributed(layers.Dense(n_features))(x)

    model = Model(inputs=inp, outputs=decoded)
    model.compile(optimizer=optimizers.Adam(LEARNING_RATE), loss="mae")
    return model


def _sliding_windows(arr: np.ndarray, window: int) -> np.ndarray:
    """Convert a 1-D array into overlapping sliding windows of shape (N, window, 1)."""
    out = []
    for i in range(len(arr) - window):
        out.append(arr[i:i + window])
    return np.array(out)[..., np.newaxis]


# ──────────────────────────────────────────────────────────────
class LSTMAutoencoderDetector:
    """
    Online LSTM Autoencoder anomaly detector.
    Usage:
        detector = LSTMAutoencoderDetector()
        detector.fit(historical_values)      # offline train
        result = detector.update(new_value)  # online inference
    """

    def __init__(self):
        self.seq_len        = SEQUENCE_LENGTH
        self.model          = None
        self.threshold      = None
        self.mean_error     = None
        self.std_error      = None
        self._trained       = False
        self.window: deque  = deque(maxlen=self.seq_len)
        self.buffer: list   = []

        self._load()

    # ── Persistence ──────────────────────────────────────────
    def save(self):
        os.makedirs(SAVED_MODEL_DIR, exist_ok=True)
        self.model.save_weights(WEIGHTS_PATH)
        cfg = {
            "threshold":  self.threshold,
            "mean_error": self.mean_error,
            "std_error":  self.std_error,
            "seq_len":    self.seq_len,
        }
        with open(CONFIG_PATH, "w") as f:
            json.dump(cfg, f)
        logger.info("💾 LSTM AE model saved.")

    def _load(self):
        if os.path.exists(CONFIG_PATH) and os.path.exists(WEIGHTS_PATH):
            try:
                with open(CONFIG_PATH) as f:
                    cfg = json.load(f)
                self.threshold  = cfg["threshold"]
                self.mean_error = cfg["mean_error"]
                self.std_error  = cfg["std_error"]
                self.seq_len    = cfg["seq_len"]
                self.model = _build_model(self.seq_len, 1)
                self.model.load_weights(WEIGHTS_PATH)
                self._trained = True
                logger.info("✅ LSTM AE loaded from disk.")
            except Exception as e:
                logger.warning("Could not load LSTM AE: %s", e)

    # ── Training ─────────────────────────────────────────────
    def fit(self, historical_values: list[float]):
        logger.info("Training LSTM Autoencoder on %d samples…", len(historical_values))
        arr = np.array(historical_values, dtype=np.float32)
        # Min-max normalise
        self._min = arr.min()
        self._max = arr.max() + 1e-9
        arr = (arr - self._min) / (self._max - self._min)

        X = _sliding_windows(arr, self.seq_len)          # (N, seq_len, 1)

        self.model = _build_model(self.seq_len, 1)

        import tensorflow as tf
        early_stop = tf.keras.callbacks.EarlyStopping(
            monitor="val_loss", patience=5, restore_best_weights=True
        )
        self.model.fit(
            X, X,
            epochs=EPOCHS,
            batch_size=BATCH_SIZE,
            validation_split=0.1,
            callbacks=[early_stop],
            verbose=1,
        )

        # Compute reconstruction errors on training data → set threshold
        recon      = self.model.predict(X, verbose=0)
        errors     = np.mean(np.abs(X - recon), axis=(1, 2))
        self.mean_error = float(errors.mean())
        self.std_error  = float(errors.std())
        self.threshold  = self.mean_error + THRESHOLD_SIGMA * self.std_error
        self._trained   = True
        logger.info("Threshold set to %.6f  (mean=%.4f  std=%.4f)",
                    self.threshold, self.mean_error, self.std_error)
        self.save()

    def _auto_fit(self):
        if len(self.buffer) >= 1000:
            self.fit(self.buffer)
            self.buffer = []

    # ── Normalisation (online) ────────────────────────────────
    def _norm(self, v: float) -> float:
        if not hasattr(self, "_min"):
            return v
        return (v - self._min) / (self._max - self._min)

    # ── Inference ────────────────────────────────────────────
    def update(self, value: float) -> dict:
        """Process one new reading and return an anomaly result dict."""
        self.window.append(self._norm(value))

        if not self._trained:
            self.buffer.append(value)
            self._auto_fit()
            return {"is_anomaly": False, "score": 0.0,
                    "method": "lstm_autoencoder", "status": "warming_up"}

        if len(self.window) < self.seq_len:
            return {"is_anomaly": False, "score": 0.0,
                    "method": "lstm_autoencoder", "status": "filling_window"}

        seq = np.array(list(self.window), dtype=np.float32).reshape(1, self.seq_len, 1)
        recon = self.model.predict(seq, verbose=0)
        error = float(np.mean(np.abs(seq - recon)))

        # Normalised anomaly score: 0 = perfectly normal, 1 = at threshold, >1 = anomalous
        normalised_score = error / (self.threshold + 1e-9)

        return {
            "is_anomaly":       error > self.threshold,
            "score":            round(error, 6),
            "normalised_score": round(normalised_score, 4),
            "threshold":        round(self.threshold, 6),
            "method":           "lstm_autoencoder",
            "status":           "ok",
        }
