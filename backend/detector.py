"""
detector.py — Fault Detection Engine
Multi-strategy: Rule-based + Z-score + Isolation Forest
"""

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib, os, logging
from database import utcnow
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

MODEL_DIR = os.getenv("MODEL_DIR", os.path.join(os.path.dirname(__file__), "models"))
os.makedirs(MODEL_DIR, exist_ok=True)

THRESHOLDS = {
    "temperature": {"min": -10, "max": 120, "warn_high": 85,  "warn_low": 5},
    "vibration":   {"min": 0,   "max": 50,  "warn_high": 35,  "warn_low": 0},
    "pressure":    {"min": 0,   "max": 200, "warn_high": 170, "warn_low": 10},
    "current":     {"min": 0,   "max": 100, "warn_high": 80,  "warn_low": 0},
    "voltage":     {"min": 200, "max": 260, "warn_high": 250, "warn_low": 210},
    "humidity":    {"min": 0,   "max": 100, "warn_high": 90,  "warn_low": 5},
}

SEVERITY_ORDER = ["critical", "high", "medium", "low", "normal"]

RECOMMENDATIONS = {
    "critical": "Immediate shutdown required. Inspect equipment now.",
    "high":     "Schedule urgent maintenance within 24 hours.",
    "medium":   "Log event. Plan maintenance in next cycle.",
    "low":      "Within tolerance. Continue monitoring.",
    "normal":   "Operating normally.",
}


class FaultDetector:
    def __init__(self, sensor_type: str = "temperature", contamination: float = 0.05):
        self.sensor_type   = sensor_type
        self.contamination = contamination
        self.scaler        = StandardScaler()
        self.model         = IsolationForest(
            contamination=contamination, n_estimators=200, random_state=42)
        self.is_trained    = False
        self.history: List[float] = []
        self._load()

    # ── Public API ─────────────────────────────────────────────────────────────
    def seed_history(self, values: List[float]) -> None:
        """Seed the rolling z-score window from past readings (e.g. loaded
        from the database) so statistical detection has context immediately
        after a process restart instead of starting cold. No-op once the
        detector already has history, so a restart only seeds once."""
        if self.history or not values:
            return
        self.history = list(values)[-1000:]

    def train(self, data: List[float]) -> Dict:
        if len(data) < 20:
            return {"success": False, "error": "Need ≥ 20 samples"}
        X = np.array(data).reshape(-1, 1)
        self.scaler.fit(X)
        self.model.fit(self.scaler.transform(X))
        self.is_trained = True
        self._save()
        return {"success": True, "n_samples": len(data),
                "mean": round(float(np.mean(data)), 3),
                "std":  round(float(np.std(data)),  3)}

    def detect(self, value: float, timestamp: Optional[str] = None) -> Dict:
        ts = timestamp or utcnow().isoformat()
        self.history.append(value)
        if len(self.history) > 1000:
            self.history = self.history[-1000:]

        rule = self._rule(value)
        stat = self._stat(value)
        ml   = self._ml(value) if self.is_trained else {"status": "not_trained"}

        severity = self._worst(rule["status"], stat["status"], ml["status"])
        is_fault = severity in ("critical", "high", "medium")

        return {
            "timestamp":      ts,
            "value":          value,
            "sensor_type":    self.sensor_type,
            "is_fault":       is_fault,
            "severity":       severity,
            "recommendation": RECOMMENDATIONS.get(severity, ""),
            "details":        {"rule": rule, "statistical": stat, "ml": ml},
        }

    def batch_detect(self, values: List[float],
                     timestamps: Optional[List[str]] = None) -> List[Dict]:
        return [self.detect(v, timestamps[i] if timestamps else None)
                for i, v in enumerate(values)]

    # ── Strategies ─────────────────────────────────────────────────────────────
    def _rule(self, v: float) -> Dict:
        t = THRESHOLDS.get(self.sensor_type, {})
        if not t:
            return {"status": "normal", "msg": "No thresholds defined"}
        if v > t["max"] or v < t["min"]:
            return {"status": "critical", "msg": f"{v} outside absolute range [{t['min']}, {t['max']}]"}
        if v > t["warn_high"]:
            return {"status": "high",     "msg": f"{v} above warning limit {t['warn_high']}"}
        if v < t["warn_low"]:
            return {"status": "medium",   "msg": f"{v} below warning limit {t['warn_low']}"}
        return {"status": "normal", "msg": "Within range"}

    def _stat(self, v: float) -> Dict:
        if len(self.history) < 10:
            return {"status": "normal", "z_score": None, "msg": "Insufficient history"}
        arr  = np.array(self.history[-100:])
        mean = float(np.mean(arr))
        std  = float(np.std(arr)) or 1e-9
        z    = abs((v - mean) / std)
        if   z > 4.0: status = "critical"
        elif z > 3.0: status = "high"
        elif z > 2.5: status = "medium"
        elif z > 2.0: status = "low"
        else:         status = "normal"
        return {"status": status, "z_score": round(z, 3),
                "mean": round(mean, 3), "std": round(std, 3)}

    def _ml(self, v: float) -> Dict:
        try:
            X    = self.scaler.transform([[v]])
            pred = self.model.predict(X)[0]
            score= float(self.model.score_samples(X)[0])
            anom = bool(pred == -1)  # numpy.bool_ isn't JSON-serializable; cast to a native bool
            status = ("critical" if anom and score < -0.3
                      else "high" if anom else "normal")
            return {"status": status, "score": round(score, 4), "anomaly": anom}
        except Exception as e:
            return {"status": "normal", "error": str(e)}

    # ── Helpers ────────────────────────────────────────────────────────────────
    def _worst(self, *statuses: str) -> str:
        for level in SEVERITY_ORDER:
            if level in statuses:
                return level
        return "normal"

    def _model_path(self, name: str) -> str:
        return os.path.join(MODEL_DIR, f"{self.sensor_type}_{name}.pkl")

    def _save(self):
        joblib.dump(self.scaler, self._model_path("scaler"))
        joblib.dump(self.model,  self._model_path("iforest"))
        logger.info(f"Model saved for {self.sensor_type}")

    def _load(self):
        sp = self._model_path("scaler")
        mp = self._model_path("iforest")
        if os.path.exists(sp) and os.path.exists(mp):
            self.scaler     = joblib.load(sp)
            self.model      = joblib.load(mp)
            self.is_trained = True
            logger.info(f"Model loaded for {self.sensor_type}")


# ── Per-sensor detector registry ─────────────────────────────────────────────
_registry: Dict[str, FaultDetector] = {}

def get_detector(sensor_type: str) -> FaultDetector:
    if sensor_type not in _registry:
        _registry[sensor_type] = FaultDetector(sensor_type)
    return _registry[sensor_type]