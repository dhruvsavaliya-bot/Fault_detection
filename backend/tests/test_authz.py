"""tests/test_authz.py — role-based access control.

FaultSense is a shared team tool (everyone sees the same sensors/faults/
alerts), but reconfiguring the monitoring setup itself — adding sensors,
training models, deleting sensors — is gated by role. See authz.py.
"""

from flask_jwt_extended import create_access_token
from app import app as flask_app
from database import db, User


def _token_with_role(role, username):
    with flask_app.app_context():
        user = User(username=username, email=f"{username}@example.com",
                    password_hash="x", role=role)
        db.session.add(user)
        db.session.commit()
        token = create_access_token(identity=str(user.id))
    return {"Authorization": f"Bearer {token}"}


def test_operator_cannot_create_sensor(client, auth_token):
    resp = client.post("/api/sensors", headers=auth_token, json={
        "name": "Should Not Exist", "sensor_type": "temperature",
    })
    assert resp.status_code == 403


def test_engineer_can_create_sensor(client):
    headers = _token_with_role("engineer", "authz_engineer_create")
    resp = client.post("/api/sensors", headers=headers, json={
        "name": "Engineer Sensor", "sensor_type": "temperature",
    })
    assert resp.status_code == 201


def test_admin_can_create_sensor(client, admin_token):
    resp = client.post("/api/sensors", headers=admin_token, json={
        "name": "Admin Sensor", "sensor_type": "temperature",
    })
    assert resp.status_code == 201


def test_operator_cannot_train_model(client, auth_token):
    resp = client.post("/api/train/temperature", headers=auth_token, json={"values": [1.0] * 30})
    assert resp.status_code == 403


def test_engineer_can_train_model(client):
    headers = _token_with_role("engineer", "authz_engineer_train")
    resp = client.post("/api/train/vibration", headers=headers, json={"values": [1.0] * 30})
    assert resp.status_code == 200


def test_operator_cannot_delete_sensor(client, auth_token, admin_token):
    created = client.post("/api/sensors", headers=admin_token, json={
        "name": "Delete Target", "sensor_type": "humidity",
    })
    sid = created.get_json()["id"]

    resp = client.delete(f"/api/sensors/{sid}", headers=auth_token)
    assert resp.status_code == 403


def test_engineer_cannot_delete_sensor_only_admin_can(client, admin_token):
    created = client.post("/api/sensors", headers=admin_token, json={
        "name": "Delete Target 2", "sensor_type": "humidity",
    })
    sid = created.get_json()["id"]

    engineer_headers = _token_with_role("engineer", "authz_engineer_delete")
    denied = client.delete(f"/api/sensors/{sid}", headers=engineer_headers)
    assert denied.status_code == 403

    allowed = client.delete(f"/api/sensors/{sid}", headers=admin_token)
    assert allowed.status_code == 200


def test_operator_can_still_view_and_resolve(client, auth_token, admin_token):
    """Role gating only covers reconfiguring the setup — day-to-day
    operation (viewing, submitting readings, resolving faults, alerts)
    stays open to every authenticated role."""
    created = client.post("/api/sensors", headers=admin_token, json={
        "name": "Operator View Target", "sensor_type": "pressure",
    })
    sid = created.get_json()["id"]

    assert client.get("/api/sensors", headers=auth_token).status_code == 200
    assert client.post(f"/api/sensors/{sid}/readings", headers=auth_token,
                        json={"value": 999}).status_code == 201

    faults = client.get("/api/faults", headers=auth_token).get_json()
    fid = next(f["id"] for f in faults if f["sensor_id"] == sid)
    assert client.put(f"/api/faults/{fid}/resolve", headers=auth_token).status_code == 200
