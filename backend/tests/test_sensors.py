"""tests/test_sensors.py — sensor CRUD, readings, and live-detection fields."""


def test_list_sensors_requires_auth(client):
    resp = client.get("/api/sensors")
    assert resp.status_code == 401


def test_seeded_sensors_present_with_summary_fields(client, auth_token):
    resp = client.get("/api/sensors", headers=auth_token)
    assert resp.status_code == 200
    sensors = resp.get_json()
    # other tests in this session may have created additional sensors against
    # the same shared database, so assert on the known seed set as a subset
    names = {s["name"] for s in sensors}
    assert {"Motor Temp A", "Pump Vibration", "Line Pressure"} <= names

    s = sensors[0]
    for field in ("id", "name", "sensor_type", "location", "unit", "latest_value", "status"):
        assert field in s


def test_create_sensor_and_add_reading(client, auth_token, admin_token):
    # creating a sensor is an admin/engineer action; reading/operating it is not
    created = client.post("/api/sensors", headers=admin_token, json={
        "name": "Test Rig Temp", "sensor_type": "temperature",
        "location": "Lab", "unit": "C",
    })
    assert created.status_code == 201
    sid = created.get_json()["id"]

    normal = client.post(f"/api/sensors/{sid}/readings", headers=auth_token, json={"value": 50})
    assert normal.status_code == 201
    assert normal.get_json()["is_fault"] is False

    spike = client.post(f"/api/sensors/{sid}/readings", headers=auth_token, json={"value": 999})
    assert spike.status_code == 201
    body = spike.get_json()
    assert body["is_fault"] is True
    assert body["severity"] == "critical"

    detail = client.get(f"/api/sensors/{sid}", headers=auth_token)
    data = detail.get_json()
    assert data["latest_value"] == 999.0
    assert data["status"] == "critical"
    assert data["total_readings"] == 2
    assert data["open_faults"] == 1


def test_resolving_fault_clears_sensor_status(client, auth_token, admin_token):
    created = client.post("/api/sensors", headers=admin_token, json={
        "name": "Resolve Test Sensor", "sensor_type": "pressure",
    })
    sid = created.get_json()["id"]
    client.post(f"/api/sensors/{sid}/readings", headers=auth_token, json={"value": 999})

    faults = client.get("/api/faults", headers=auth_token).get_json()
    fault_id = next(f["id"] for f in faults if f["sensor_id"] == sid)

    resolved = client.put(f"/api/faults/{fault_id}/resolve", headers=auth_token)
    assert resolved.status_code == 200

    detail = client.get(f"/api/sensors/{sid}", headers=auth_token).get_json()
    assert detail["open_faults"] == 0
    assert detail["status"] == "normal"
