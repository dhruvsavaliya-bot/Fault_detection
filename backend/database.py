"""
database.py — SQLAlchemy models & DB initialisation
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash
import json

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80),  unique=True, nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role          = db.Column(db.String(20),  default="operator")
    created_at    = db.Column(db.DateTime,    default=datetime.utcnow)
    is_active     = db.Column(db.Boolean,     default=True)

    def to_dict(self):
        return {"id": self.id, "username": self.username,
                "email": self.email, "role": self.role,
                "created_at": self.created_at.isoformat()}


class Sensor(db.Model):
    __tablename__ = "sensors"
    id            = db.Column(db.Integer,     primary_key=True)
    name          = db.Column(db.String(100), nullable=False)
    sensor_type   = db.Column(db.String(50),  nullable=False)
    location      = db.Column(db.String(100))
    unit          = db.Column(db.String(20))
    is_active     = db.Column(db.Boolean,     default=True)
    created_at    = db.Column(db.DateTime,    default=datetime.utcnow)
    readings      = db.relationship("SensorReading", backref="sensor", lazy=True)
    faults        = db.relationship("Fault",          backref="sensor", lazy=True)

    def to_dict(self):
        return {"id": self.id, "name": self.name,
                "sensor_type": self.sensor_type, "location": self.location,
                "unit": self.unit, "is_active": self.is_active}


class SensorReading(db.Model):
    __tablename__ = "sensor_readings"
    id            = db.Column(db.Integer,   primary_key=True)
    sensor_id     = db.Column(db.Integer,   db.ForeignKey("sensors.id"), nullable=False)
    value         = db.Column(db.Float,     nullable=False)
    timestamp     = db.Column(db.DateTime,  default=datetime.utcnow)
    is_anomaly    = db.Column(db.Boolean,   default=False)

    def to_dict(self):
        return {"id": self.id, "sensor_id": self.sensor_id,
                "value": self.value,
                "timestamp": self.timestamp.isoformat(),
                "is_anomaly": self.is_anomaly}


class Fault(db.Model):
    __tablename__ = "faults"
    id            = db.Column(db.Integer,     primary_key=True)
    sensor_id     = db.Column(db.Integer,     db.ForeignKey("sensors.id"), nullable=False)
    severity      = db.Column(db.String(20),  nullable=False)
    fault_type    = db.Column(db.String(100))
    value         = db.Column(db.Float)
    description   = db.Column(db.Text)
    recommendation= db.Column(db.Text)
    status        = db.Column(db.String(20),  default="open")
    detected_at   = db.Column(db.DateTime,    default=datetime.utcnow)
    resolved_at   = db.Column(db.DateTime,    nullable=True)
    details_json  = db.Column(db.Text,        default="{}")

    def to_dict(self):
        return {
            "id": self.id,
            "sensor_id": self.sensor_id,
            "sensor_name": self.sensor.name if self.sensor else None,
            "severity": self.severity,
            "fault_type": self.fault_type,
            "value": self.value,
            "description": self.description,
            "recommendation": self.recommendation,
            "status": self.status,
            "detected_at": self.detected_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "details": json.loads(self.details_json or "{}")
        }


class Alert(db.Model):
    __tablename__ = "alerts"
    id            = db.Column(db.Integer,    primary_key=True)
    fault_id      = db.Column(db.Integer,    db.ForeignKey("faults.id"))
    message       = db.Column(db.Text,       nullable=False)
    severity      = db.Column(db.String(20))
    is_read       = db.Column(db.Boolean,    default=False)
    created_at    = db.Column(db.DateTime,   default=datetime.utcnow)

    def to_dict(self):
        return {"id": self.id, "fault_id": self.fault_id,
                "message": self.message, "severity": self.severity,
                "is_read": self.is_read,
                "created_at": self.created_at.isoformat()}


def init_db():
    db.create_all()
    _seed_demo_data()


def _seed_demo_data():
    if Sensor.query.first():
        return

    if not User.query.first():
        admin = User(
            username="admin",
            email="admin@example.com",
            password_hash=generate_password_hash("admin123"),
            role="admin",
        )
        db.session.add(admin)

    sensors = [
        Sensor(name="Motor Temp A",    sensor_type="temperature", location="Zone A", unit="°C"),
        Sensor(name="Pump Vibration",  sensor_type="vibration",   location="Zone B", unit="mm/s"),
        Sensor(name="Line Pressure",   sensor_type="pressure",    location="Zone C", unit="bar"),
        Sensor(name="Drive Current",   sensor_type="current",     location="Zone A", unit="A"),
        Sensor(name="Supply Voltage",  sensor_type="voltage",     location="Zone D", unit="V"),
        Sensor(name="Ambient Humidity",sensor_type="humidity",    location="Zone B", unit="%"),
    ]
    db.session.add_all(sensors)
    db.session.commit()