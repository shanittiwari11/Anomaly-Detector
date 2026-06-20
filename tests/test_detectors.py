"""
tests/test_detectors.py
-----------------------
Unit tests for both anomaly detection models.
Run: pytest tests/ -v
"""

import random
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pytest

from models.isolation_forest import IsolationForestDetector, extract_features
from collections import deque


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────
def make_normal_data(n: int = 1000) -> list[float]:
    return [random.gauss(70, 5) for _ in range(n)]


def make_anomaly(mean: float = 70.0) -> float:
    return mean + random.uniform(50, 80)


# ──────────────────────────────────────────────────────────────
# extract_features
# ──────────────────────────────────────────────────────────────
class TestExtractFeatures:
    def test_shape(self):
        w = deque([70.0, 71.0, 69.5], maxlen=20)
        feats = extract_features(72.0, w)
        assert feats.shape == (1, 7), f"Expected (1,7), got {feats.shape}"

    def test_empty_window(self):
        w = deque(maxlen=20)
        feats = extract_features(70.0, w)
        assert feats.shape == (1, 7)

    def test_zscore_normal(self):
        w = deque([70.0] * 19, maxlen=20)
        feats = extract_features(70.0, w)
        z_score = feats[0, 5]
        assert abs(z_score) < 0.01, "z-score of mean value should be ~0"

    def test_zscore_spike(self):
        w = deque([70.0] * 19, maxlen=20)
        feats = extract_features(200.0, w)
        z_score = feats[0, 5]
        assert z_score > 5, "High spike should give high z-score"


# ──────────────────────────────────────────────────────────────
# IsolationForestDetector
# ──────────────────────────────────────────────────────────────
class TestIsolationForestDetector:
    def _trained_detector(self):
        detector = IsolationForestDetector(contamination=0.05)
        detector.fit(make_normal_data(1000))
        return detector

    def test_fit_returns_trained(self):
        d = self._trained_detector()
        assert d._trained is True

    def test_normal_not_anomaly(self):
        d = self._trained_detector()
        # Warm up window
        for _ in range(25):
            d.update(random.gauss(70, 5))
        # Test several normal values
        anomaly_count = sum(
            1 for _ in range(50) if d.update(random.gauss(70, 5))["is_anomaly"]
        )
        # Allow up to 15% false positive rate on normal data
        assert anomaly_count <= 8, f"Too many false positives: {anomaly_count}/50"

    def test_spike_detected(self):
        d = self._trained_detector()
        for _ in range(25):
            d.update(random.gauss(70, 5))
        # A massive spike should always be detected
        result = d.update(500.0)
        assert result["is_anomaly"] is True, "500°C spike should be an anomaly"

    def test_result_keys(self):
        d = self._trained_detector()
        for _ in range(25):
            d.update(70.0)
        r = d.update(70.0)
        assert "is_anomaly" in r
        assert "score" in r
        assert "method" in r
        assert r["method"] == "isolation_forest"

    def test_warming_up_status(self):
        d = IsolationForestDetector()   # not yet fitted
        r = d.update(70.0)
        assert r["status"] == "warming_up"

    def test_score_is_float(self):
        d = self._trained_detector()
        for _ in range(25):
            d.update(70.0)
        r = d.update(72.0)
        assert isinstance(r["score"], float)


# ──────────────────────────────────────────────────────────────
# Producer message structure
# ──────────────────────────────────────────────────────────────
class TestProducerMessage:
    def test_message_schema(self):
        import sys
        sys.path.insert(0, "producer")
        from sensor_simulator import build_message
        msg = build_message()
        assert "sensor_id"  in msg
        assert "timestamp"  in msg
        assert "readings"   in msg
        assert isinstance(msg["readings"], dict)
        for ch in ["temperature", "vibration", "pressure"]:
            assert ch in msg["readings"]
            assert "value" in msg["readings"][ch]
            assert "unit"  in msg["readings"][ch]

    def test_anomaly_channels_subset(self):
        from sensor_simulator import build_message
        msg = build_message()
        channels = set(msg["readings"].keys())
        for a in msg["anomaly_channels"]:
            assert a in channels


# ──────────────────────────────────────────────────────────────
# Consumer processing
# ──────────────────────────────────────────────────────────────
class TestChannelDetectorRegistry:
    def test_creates_detector_per_channel(self):
        import sys
        sys.path.insert(0, "consumer")
        from kafka_consumer import ChannelDetectorRegistry
        reg = ChannelDetectorRegistry("isolation_forest")
        d1 = reg.get("sensor-1::temperature")
        d2 = reg.get("sensor-1::vibration")
        d3 = reg.get("sensor-1::temperature")   # should return same instance
        assert d1 is not d2
        assert d1 is d3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
