"""
evaluate_models.py
------------------
Runs both models against a labelled synthetic dataset and prints a
side-by-side comparison report.

Usage:
    python scripts/evaluate_models.py
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import random
import time
import numpy as np

# ──────────────────────────────────────────────────────────────
# Dataset generation
# ──────────────────────────────────────────────────────────────
def make_dataset(n: int = 2000, anomaly_frac: float = 0.05):
    """Returns (values, labels) where label 1 = anomaly."""
    values, labels = [], []
    for _ in range(n):
        if random.random() < anomaly_frac:
            # Mix of spike and drift anomalies
            if random.random() < 0.6:
                v = random.gauss(70, 5) + random.uniform(35, 70)   # spike
            else:
                v = random.gauss(70, 5) + random.uniform(15, 30)   # drift-like
            labels.append(1)
        else:
            v = random.gauss(70, 5)
            labels.append(0)
        values.append(round(v, 3))
    return values, labels


# ──────────────────────────────────────────────────────────────
# Metrics
# ──────────────────────────────────────────────────────────────
def compute_metrics(y_true, y_pred):
    TP = sum(t == 1 and p == 1 for t, p in zip(y_true, y_pred))
    FP = sum(t == 0 and p == 1 for t, p in zip(y_true, y_pred))
    FN = sum(t == 1 and p == 0 for t, p in zip(y_true, y_pred))
    TN = sum(t == 0 and p == 0 for t, p in zip(y_true, y_pred))

    precision = TP / max(TP + FP, 1)
    recall    = TP / max(TP + FN, 1)
    f1        = 2 * precision * recall / max(precision + recall, 1e-9)
    fpr       = FP / max(FP + TN, 1)
    accuracy  = (TP + TN) / max(len(y_true), 1)
    return {"precision": precision, "recall": recall, "f1": f1,
            "fpr": fpr, "accuracy": accuracy, "TP": TP, "FP": FP, "FN": FN, "TN": TN}


# ──────────────────────────────────────────────────────────────
# Evaluate one model
# ──────────────────────────────────────────────────────────────
def evaluate(detector, values, labels):
    # First 500 points used for auto-fit / warm-up
    preds = []
    t0 = time.perf_counter()
    for v in values:
        r = detector.update(v)
        preds.append(1 if r.get("is_anomaly") else 0)
    elapsed = time.perf_counter() - t0
    # Skip warm-up period from metrics
    skip = 500
    metrics = compute_metrics(labels[skip:], preds[skip:])
    metrics["latency_ms"] = round(1000 * elapsed / len(values), 3)
    return metrics


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────
def main():
    print("\n" + "═" * 60)
    print("  MODEL COMPARISON REPORT")
    print("═" * 60)

    # Generate data
    TRAIN_N = 3000
    TEST_N  = 2000
    print(f"\n📦 Generating training data ({TRAIN_N} samples)…")
    train_vals, _       = make_dataset(TRAIN_N, anomaly_frac=0.0)  # clean train
    print(f"📦 Generating test data    ({TEST_N} samples, 5% anomalies)…")
    test_vals, test_labels = make_dataset(TEST_N, anomaly_frac=0.05)

    results = {}

    # ── Isolation Forest ─────────────────────────────────────
    print("\n[1/2] Training Isolation Forest…")
    from models.isolation_forest import IsolationForestDetector
    if_det = IsolationForestDetector()
    if_det.fit(train_vals)
    results["IsolationForest"] = evaluate(if_det, test_vals, test_labels)

    # ── LSTM AE ──────────────────────────────────────────────
    print("[2/2] Training LSTM Autoencoder…")
    try:
        from models.lstm_autoencoder import LSTMAutoencoderDetector
        lstm_det = LSTMAutoencoderDetector()
        lstm_det.fit(train_vals)
        results["LSTM_AE"] = evaluate(lstm_det, test_vals, test_labels)
    except Exception as e:
        print(f"  LSTM skipped (TensorFlow not installed?): {e}")

    # ── Print table ───────────────────────────────────────────
    header = f"\n{'Metric':<18}" + "".join(f"{k:>18}" for k in results)
    print(header)
    print("─" * (18 + 18 * len(results)))
    for metric in ("precision", "recall", "f1", "accuracy", "fpr", "latency_ms"):
        row = f"{metric:<18}"
        for k in results:
            v = results[k][metric]
            if metric == "latency_ms":
                row += f"{v:>17.3f}ms"
            else:
                row += f"{v:>17.3%}" if v <= 1.0 else f"{v:>18}"
        print(row)

    # ── Summary ───────────────────────────────────────────────
    if "IsolationForest" in results and "LSTM_AE" in results:
        if_f1   = results["IsolationForest"]["f1"]
        lstm_f1 = results["LSTM_AE"]["f1"]
        diff    = abs(lstm_f1 - if_f1)
        winner  = "LSTM_AE" if lstm_f1 > if_f1 else "IsolationForest"
        print(f"\n🏆 F1 winner: {winner}  (+{diff:.1%} better on F1)")

    print("\n" + "═" * 60 + "\n")


if __name__ == "__main__":
    main()
