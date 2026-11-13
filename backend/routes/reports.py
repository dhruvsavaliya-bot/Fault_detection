"""
routes/reports.py — Reports & analytics endpoints
"""

from flask import Blueprint, jsonify, Response, request
from flask_jwt_extended import jwt_required
from database import db, Fault, SensorReading, Sensor, Alert, utcnow
from datetime import timedelta
import csv, io

reports_bp = Blueprint("reports", __name__)


@reports_bp.route("/analytics", methods=["GET"])
@jwt_required()
def analytics():
    days = int(request.args.get("days", 7))
    since = utcnow() - timedelta(days=days)

    faults = Fault.query.filter(Fault.detected_at >= since).all()

    by_severity = {}
    by_day      = {}
    by_sensor   = {}

    for f in faults:
        by_severity[f.severity] = by_severity.get(f.severity, 0) + 1
        day = f.detected_at.strftime("%Y-%m-%d")
        by_day[day]             = by_day.get(day, 0) + 1
        by_sensor[f.sensor_id]  = by_sensor.get(f.sensor_id, 0) + 1

    sensor_names = {}
    for s in Sensor.query.all():
        sensor_names[s.id] = s.name

    by_sensor_named = {sensor_names.get(k, f"S{k}"): v
                       for k, v in by_sensor.items()}

    return jsonify({
        "period_days":  days,
        "total_faults": len(faults),
        "by_severity":  by_severity,
        "by_day":       dict(sorted(by_day.items())),
        "by_sensor":    by_sensor_named,
        "resolution_rate": _resolution_rate(since),
    }), 200


@reports_bp.route("/export/csv", methods=["GET"])
@jwt_required()
def export_csv():
    days  = int(request.args.get("days", 30))
    since = utcnow() - timedelta(days=days)
    faults= Fault.query.filter(Fault.detected_at >= since).all()

    buf = io.StringIO()
    w   = csv.writer(buf)
    w.writerow(["ID", "Sensor ID", "Severity", "Fault Type",
                "Value", "Description", "Status", "Detected At", "Resolved At"])
    for f in faults:
        w.writerow([f.id, f.sensor_id, f.severity, f.fault_type,
                    f.value, f.description, f.status,
                    f.detected_at.isoformat(),
                    f.resolved_at.isoformat() if f.resolved_at else ""])

    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=faults_{days}d.csv"},
    )


@reports_bp.route("/export/readings/csv", methods=["GET"])
@jwt_required()
def export_readings_csv():
    sid   = request.args.get("sensor_id", type=int)
    limit = int(request.args.get("limit", 1000))
    q     = SensorReading.query
    if sid:
        q = q.filter_by(sensor_id=sid)
    readings = q.order_by(SensorReading.timestamp.desc()).limit(limit).all()

    buf = io.StringIO()
    w   = csv.writer(buf)
    w.writerow(["ID", "Sensor ID", "Value", "Timestamp", "Is Anomaly"])
    for r in readings:
        w.writerow([r.id, r.sensor_id, r.value,
                    r.timestamp.isoformat(), r.is_anomaly])

    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=readings.csv"},
    )


def _resolution_rate(since: datetime) -> float:
    total    = Fault.query.filter(Fault.detected_at >= since).count()
    resolved = Fault.query.filter(
        Fault.detected_at >= since,
        Fault.status == "resolved"
    ).count()
    return round((resolved / total * 100) if total else 0, 1)
