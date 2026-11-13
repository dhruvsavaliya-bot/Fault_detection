"""
routes/api.py — Core REST API: sensors, readings, faults, alerts
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database import db, Sensor, SensorReading, Fault, Alert, utcnow
from detector import get_detector
from extensions import socketio
from authz import require_role
from datetime import timedelta
import random, json

api_bp = Blueprint("api", __name__)


# ── Sensors ───────────────────────────────────────────────────────────────────
def _sensor_status(sensor_id):
    """Most recent open fault severity for a sensor, or 'critical'/'fault'/'normal'."""
    open_fault = (Fault.query
                  .filter_by(sensor_id=sensor_id, status="open")
                  .order_by(Fault.detected_at.desc())
                  .first())
    if not open_fault:
        return "normal"
    return "critical" if open_fault.severity == "critical" else "fault"


def _sensor_summary(sensor):
    data = sensor.to_dict()
    latest = (SensorReading.query
              .filter_by(sensor_id=sensor.id)
              .order_by(SensorReading.timestamp.desc())
              .first())
    data["latest_value"]     = latest.value if latest else None
    data["latest_timestamp"] = latest.timestamp.isoformat() if latest else None
    data["status"]           = _sensor_status(sensor.id)
    return data


@api_bp.route("/sensors", methods=["GET"])
@jwt_required()
def list_sensors():
    sensors = Sensor.query.filter_by(is_active=True).all()
    return jsonify([_sensor_summary(s) for s in sensors]), 200


@api_bp.route("/sensors", methods=["POST"])
@require_role("admin", "engineer")
def create_sensor():
    data   = request.get_json()
    sensor = Sensor(
        name        = data["name"],
        sensor_type = data["sensor_type"],
        location    = data.get("location", ""),
        unit        = data.get("unit", ""),
    )
    db.session.add(sensor)
    db.session.commit()
    return jsonify(sensor.to_dict()), 201


@api_bp.route("/sensors/<int:sid>", methods=["GET"])
@jwt_required()
def get_sensor(sid):
    sensor = Sensor.query.get_or_404(sid)
    data   = _sensor_summary(sensor)
    data["total_readings"] = SensorReading.query.filter_by(sensor_id=sid).count()
    data["open_faults"]    = Fault.query.filter_by(sensor_id=sid, status="open").count()
    return jsonify(data), 200


@api_bp.route("/sensors/<int:sid>", methods=["DELETE"])
@require_role("admin")
def delete_sensor(sid):
    sensor            = Sensor.query.get_or_404(sid)
    sensor.is_active  = False
    db.session.commit()
    return jsonify({"message": "Sensor deactivated"}), 200


def _seed_detector_history(detector, sensor_type):
    """On first use after a restart, give the detector's rolling z-score
    window some real context instead of starting with an empty history."""
    if detector.history:
        return
    recent = (SensorReading.query
              .join(Sensor, SensorReading.sensor_id == Sensor.id)
              .filter(Sensor.sensor_type == sensor_type)
              .order_by(SensorReading.timestamp.desc())
              .limit(200).all())
    detector.seed_history([r.value for r in reversed(recent)])


# ── Readings + Live Detection ─────────────────────────────────────────────────
@api_bp.route("/sensors/<int:sid>/readings", methods=["POST"])
@jwt_required()
def add_reading(sid):
    sensor   = Sensor.query.get_or_404(sid)
    data     = request.get_json()
    value    = float(data["value"])
    detector = get_detector(sensor.sensor_type)
    _seed_detector_history(detector, sensor.sensor_type)
    result   = detector.detect(value)

    reading  = SensorReading(
        sensor_id  = sid,
        value      = value,
        is_anomaly = result["is_fault"],
    )
    db.session.add(reading)

    if result["is_fault"]:
        fault = Fault(
            sensor_id      = sid,
            severity       = result["severity"],
            fault_type     = f"{sensor.sensor_type}_anomaly",
            value          = value,
            description    = result["details"]["rule"].get("msg", ""),
            recommendation = result["recommendation"],
            details_json   = json.dumps(result["details"]),
        )
        db.session.add(fault)
        db.session.flush()

        alert = Alert(
            fault_id = fault.id,
            message  = f"[{result['severity'].upper()}] Sensor '{sensor.name}' — {result['recommendation']}",
            severity = result["severity"],
        )
        db.session.add(alert)
        db.session.commit()

        socketio.emit("fault_detected", fault.to_dict())
    else:
        db.session.commit()

    return jsonify(result), 201


@api_bp.route("/sensors/<int:sid>/readings", methods=["GET"])
@jwt_required()
def get_readings(sid):
    limit    = int(request.args.get("limit", 100))
    readings = (SensorReading.query
                .filter_by(sensor_id=sid)
                .order_by(SensorReading.timestamp.desc())
                .limit(limit).all())
    return jsonify([r.to_dict() for r in reversed(readings)]), 200


# ── Faults ────────────────────────────────────────────────────────────────────
@api_bp.route("/faults", methods=["GET"])
@jwt_required()
def list_faults():
    status   = request.args.get("status")
    severity = request.args.get("severity")
    # keep the response a plain array (existing frontend contract) while
    # letting a caller page through more than the default cap if it needs to
    limit    = min(1000, max(1, request.args.get("limit", 200, type=int)))
    offset   = max(0, request.args.get("offset", 0, type=int))

    q = Fault.query
    if status:   q = q.filter_by(status=status)
    if severity: q = q.filter_by(severity=severity)
    faults = (q.order_by(Fault.detected_at.desc())
                .offset(offset).limit(limit).all())
    return jsonify([f.to_dict() for f in faults]), 200


@api_bp.route("/faults/<int:fid>/resolve", methods=["PUT"])
@jwt_required()
def resolve_fault(fid):
    fault             = Fault.query.get_or_404(fid)
    fault.status      = "resolved"
    fault.resolved_at = utcnow()
    db.session.commit()
    return jsonify(fault.to_dict()), 200


# ── Alerts ────────────────────────────────────────────────────────────────────
@api_bp.route("/alerts", methods=["GET"])
@jwt_required()
def list_alerts():
    limit  = min(500, max(1, request.args.get("limit", 50, type=int)))
    offset = max(0, request.args.get("offset", 0, type=int))
    alerts = (Alert.query
              .order_by(Alert.created_at.desc())
              .offset(offset).limit(limit).all())
    return jsonify([a.to_dict() for a in alerts]), 200


@api_bp.route("/alerts/<int:aid>/read", methods=["PUT"])
@jwt_required()
def mark_read(aid):
    alert         = Alert.query.get_or_404(aid)
    alert.is_read = True
    db.session.commit()
    return jsonify(alert.to_dict()), 200


@api_bp.route("/alerts/read-all", methods=["PUT"])
@jwt_required()
def mark_all_read():
    Alert.query.filter_by(is_read=False).update({"is_read": True})
    db.session.commit()
    return jsonify({"message": "All alerts marked read"}), 200


# ── Dashboard Summary ─────────────────────────────────────────────────────────
@api_bp.route("/dashboard/summary", methods=["GET"])
@jwt_required()
def dashboard_summary():
    total_sensors  = Sensor.query.filter_by(is_active=True).count()
    open_faults    = Fault.query.filter_by(status="open").count()
    critical       = Fault.query.filter_by(status="open", severity="critical").count()
    unread_alerts  = Alert.query.filter_by(is_read=False).count()
    recent_faults  = (Fault.query
                      .order_by(Fault.detected_at.desc())
                      .limit(5).all())
    return jsonify({
        "total_sensors":  total_sensors,
        "open_faults":    open_faults,
        "critical_faults":critical,
        "unread_alerts":  unread_alerts,
        "recent_faults":  [f.to_dict() for f in recent_faults],
    }), 200


# ── ML Training ───────────────────────────────────────────────────────────────
@api_bp.route("/train/<sensor_type>", methods=["POST"])
@require_role("admin", "engineer")
def train_model(sensor_type):
    data     = request.get_json()
    detector = get_detector(sensor_type)
    result   = detector.train(data.get("values", []))
    return jsonify(result), 200


# ── Demo Data Generator ───────────────────────────────────────────────────────
@api_bp.route("/demo/generate", methods=["POST"])
@jwt_required()
def generate_demo():
    """Inject simulated readings for all active sensors."""
    sensors = Sensor.query.filter_by(is_active=True).all()
    ranges  = {
        "temperature": (60, 95),
        "vibration":   (5, 40),
        "pressure":    (80, 180),
        "current":     (20, 90),
        "voltage":     (210, 255),
        "humidity":    (30, 95),
    }

    inserted = 0
    for sensor in sensors:
        lo, hi = ranges.get(sensor.sensor_type, (0, 100))
        detector = get_detector(sensor.sensor_type)
        _seed_detector_history(detector, sensor.sensor_type)
        for _ in range(20):
            v = round(random.uniform(lo, hi), 2)
            # occasionally inject spike
            if random.random() < 0.1:
                v = round(hi * random.uniform(1.05, 1.3), 2)
            result = detector.detect(v)
            reading = SensorReading(
                sensor_id  = sensor.id,
                value      = v,
                is_anomaly = result["is_fault"],
                timestamp  = utcnow() - timedelta(
                    minutes=random.randint(0, 1440))
            )
            db.session.add(reading)
            if result["is_fault"]:
                fault = Fault(
                    sensor_id      = sensor.id,
                    severity       = result["severity"],
                    fault_type     = f"{sensor.sensor_type}_anomaly",
                    value          = v,
                    description    = result["details"]["rule"].get("msg", ""),
                    recommendation = result["recommendation"],
                    details_json   = json.dumps(result["details"]),
                )
                db.session.add(fault)
                db.session.flush()

                alert = Alert(
                    fault_id = fault.id,
                    message  = f"[{result['severity'].upper()}] Sensor '{sensor.name}' — {result['recommendation']}",
                    severity = result["severity"],
                )
                db.session.add(alert)
                socketio.emit("fault_detected", fault.to_dict())
            inserted += 1
    db.session.commit()
    return jsonify({"inserted": inserted}), 201