"""
isolation_forest.py
-------------------
Wraps sklearn's IsolationForest with:
  - fit / predict / score API
  - rolling-window feature engineering
  - model persistence (joblib)
  - automatic warm-start from disk if a saved model exists
"""

import os
import logging
import numpy as np
import joblib
from collections import deque
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

SAVED_MODEL_DIR = os.getenv("SAVED_MODEL_DIR", "models/saved")
MODEL_PATH      = os.path.join(SAVED_MODEL_DIR, "isolation_forest.pkl")
SCALER_PATH     = os.path.join(SAVED_MODEL_DIR, "if_scaler.pkl")

# ──────────────────────────────────────────────────────────────
# Feature engineering helpers
# ──────────────────────────────────────────────────────────────
WINDOW = 20   # rolling window size for statistical features


def extract_features(value: float, window: deque) -> np.ndarray:
    """
    Build a feature vector from a single incoming value plus its window.
    Features:
        value, rolling_mean, rolling_std, rolling_min, rolling_max,
        z_score, delta (diff from previous)
    """
    arr = np.array(list(window)) if len(window) > 0 else np.array([value])
    mean  = float(np.mean(arr))
    std   = float(np.std(arr)) + 1e-9
    delta = float(value - arr[-1]) if len(arr) > 1 else 0.0

    return np.array([[
        value,
        mean,
        std,
        float(np.min(arr)),
        float(np.max(arr)),
        (value - mean) / std,      # z-score
        delta,
    ]])


# ──────────────────────────────────────────────────────────────
# Model class
# ──────────────────────────────────────────────────────────────
class IsolationForestDetector:
    """
    Online-compatible Isolation Forest detector.
    Call .update(value) for each new reading;
    it returns an AnomalyResult with is_anomaly, score, and features.
    """

    def __init__(self, contamination: float = 0.10, n_estimators: int = 200):
        self.contamination = contamination
        self.n_estimators  = n_estimators
        self.window: deque = deque(maxlen=WINDOW)
        self.buffer: list  = []          # pre-train buffer
        self._trained      = False

        self.model  = IsolationForest(
            n_estimators=n_estimators,
            contamination=contamination,
            random_state=42,
            n_jobs=-1,
        )
        self.scaler = StandardScaler()

        # Try loading a pre-trained model from disk
        self._load()

    # ── Persistence ──────────────────────────────────────────
    def _load(self):
        if os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH):
            try:
                self.model  = joblib.load(MODEL_PATH)
                self.scaler = joblib.load(SCALER_PATH)
                self._trained = True
                logger.info("✅ Loaded IsolationForest model from %s", MODEL_PATH)
            except Exception as e:
                logger.warning("Could not load saved model: %s", e)

    def save(self):
        os.makedirs(SAVED_MODEL_DIR, exist_ok=True)
        joblib.dump(self.model,  MODEL_PATH)
        joblib.dump(self.scaler, SCALER_PATH)
        logger.info("💾 IsolationForest model saved.")

    # ── Training ─────────────────────────────────────────────
    def fit(self, historical_values: list[float]):
        """Fit on a list of historical readings."""
        logger.info("Training IsolationForest on %d samples…", len(historical_values))
        temp_window: deque = deque(maxlen=WINDOW)
        features = []
        for v in historical_values:
            features.append(extract_features(v, temp_window).flatten())
            temp_window.append(v)

        X = np.array(features)
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled)
        self._trained = True
        self.save()
        logger.info("✅ IsolationForest trained and saved.")

    def _auto_fit(self):
        """Fit automatically once enough buffered data exists."""
        if len(self.buffer) >= 500:
            self.fit(self.buffer)
            self.buffer = []

    # ── Inference ────────────────────────────────────────────
    def update(self, value: float) -> dict:
        """
        Process a new incoming value.
        Returns a dict:
            is_anomaly (bool), score (float, lower = more anomalous), features (list)
        """
        feats = extract_features(value, self.window)
        self.window.append(value)

        if not self._trained:
            self.buffer.append(value)
            self._auto_fit()
            return {"is_anomaly": False, "score": 0.0,
                    "features": feats.flatten().tolist(), "method": "isolation_forest",
                    "status": "warming_up"}

        feats_scaled = self.scaler.transform(feats)
        label = self.model.predict(feats_scaled)[0]          # -1 anomaly, 1 normal
        score = float(self.model.score_samples(feats_scaled)[0])   # negative log-likelihood

        return {
            "is_anomaly": label == -1,
            "score":      round(score, 4),
            "features":   feats.flatten().tolist(),
            "method":     "isolation_forest",
            "status":     "ok",
        }
