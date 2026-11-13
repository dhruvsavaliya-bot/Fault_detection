"""tests/test_detector.py — unit tests for the detection engine itself.

Pure logic tests, no Flask app or database involved.
"""

import pytest
from detector import FaultDetector, get_detector


def make_detector():
    return FaultDetector(sensor_type="temperature")


def test_rule_based_thresholds():
    d = make_detector()
    assert d.detect(50)["severity"] == "normal"      # within range
    assert d.detect(90)["severity"] == "high"        # above warn_high=85
    assert d.detect(0)["severity"] == "medium"        # below warn_low=5
    assert d.detect(200)["severity"] == "critical"    # outside absolute max=120
    assert d.detect(-50)["severity"] == "critical"    # outside absolute min=-10


def test_statistical_detection_needs_history_first():
    d = make_detector()
    result = d.detect(50)
    assert result["details"]["statistical"]["status"] == "normal"
    assert result["details"]["statistical"]["z_score"] is None


def test_statistical_detection_flags_outliers_once_seeded():
    d = make_detector()
    for _ in range(30):
        d.detect(50)  # tight, stable baseline around 50
    result = d.detect(50.5)
    assert result["details"]["statistical"]["z_score"] is not None
    # a wild outlier relative to the tight baseline should be flagged
    outlier = d.detect(500)
    assert outlier["severity"] in ("critical", "high")


def test_seed_history_only_applies_once_and_is_capped():
    d = make_detector()
    d.seed_history([1.0] * 2000)
    assert len(d.history) == 1000  # capped

    d.seed_history([2.0] * 5)  # should be a no-op since history is non-empty
    assert d.history[0] == 1.0


def test_seed_history_noop_on_empty_input():
    d = make_detector()
    d.seed_history([])
    assert d.history == []


def test_train_requires_minimum_samples():
    d = make_detector()
    result = d.train([1.0] * 10)
    assert result["success"] is False


def test_train_succeeds_and_enables_ml_detection():
    d = make_detector()
    baseline = [50 + (i % 5) * 0.1 for i in range(50)]
    result = d.train(baseline)
    assert result["success"] is True
    assert result["n_samples"] == 50

    ml_result = d.detect(50)
    assert ml_result["details"]["ml"]["status"] != "not_trained"


def test_get_detector_returns_same_instance_for_same_type():
    a = get_detector("vibration")
    b = get_detector("vibration")
    assert a is b


def test_get_detector_separates_by_sensor_type():
    temp = get_detector("temperature")
    vib  = get_detector("vibration")
    assert temp is not vib
