"""tests/test_faults.py — fault listing, filtering, and pagination."""


def _create_sensor_and_fault(client, auth_token, name, sensor_type="temperature", value=999):
    created = client.post("/api/sensors", headers=auth_token, json={
        "name": name, "sensor_type": sensor_type,
    })
    sid = created.get_json()["id"]
    client.post(f"/api/sensors/{sid}/readings", headers=auth_token, json={"value": value})
    return sid


def test_faults_requires_auth(client):
    assert client.get("/api/faults").status_code == 401


def test_faults_limit_and_offset(client, admin_token):
    for i in range(5):
        _create_sensor_and_fault(client, admin_token, f"Fault Sensor {i}")

    limited = client.get("/api/faults?limit=2", headers=admin_token).get_json()
    assert len(limited) == 2

    page1 = client.get("/api/faults?limit=2&offset=0", headers=admin_token).get_json()
    page2 = client.get("/api/faults?limit=2&offset=2", headers=admin_token).get_json()
    assert {f["id"] for f in page1}.isdisjoint({f["id"] for f in page2})


def test_faults_filter_by_severity_and_status(client, admin_token):
    _create_sensor_and_fault(client, admin_token, "Severity Filter Sensor")

    critical_only = client.get("/api/faults?severity=critical", headers=admin_token).get_json()
    assert all(f["severity"] == "critical" for f in critical_only)

    open_only = client.get("/api/faults?status=open", headers=admin_token).get_json()
    assert all(f["status"] == "open" for f in open_only)


def test_resolve_fault(client, admin_token):
    sid = _create_sensor_and_fault(client, admin_token, "Resolve Flow Sensor")
    faults = client.get("/api/faults", headers=admin_token).get_json()
    fid = next(f["id"] for f in faults if f["sensor_id"] == sid)

    resp = client.put(f"/api/faults/{fid}/resolve", headers=admin_token)
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "resolved"
    assert resp.get_json()["resolved_at"] is not None
