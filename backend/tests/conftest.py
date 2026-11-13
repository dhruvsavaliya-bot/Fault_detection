"""
tests/conftest.py — shared pytest fixtures.

Runs the whole app against an isolated in-memory SQLite database and fixed
test secrets, so tests never touch backend/instance/fault_detection.db or
generate real persisted secret files.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# A real temp file rather than sqlite:///:memory: — an in-memory SQLite db is
# per-connection, so under Flask-SQLAlchemy's default pooling each request
# can silently get its own empty database. A temp file is shared correctly
# and is deleted automatically at interpreter exit.
_TEST_DB_FD, _TEST_DB_PATH = tempfile.mkstemp(suffix=".db")
os.close(_TEST_DB_FD)

os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH}"
os.environ["SECRET_KEY"]   = "test-secret-key-not-for-production"
os.environ["JWT_SECRET"]   = "test-jwt-secret-not-for-production"
os.environ["MODEL_DIR"]    = tempfile.mkdtemp(prefix="faultsense_test_models_")

import pytest
from flask_jwt_extended import create_access_token
from app import app as flask_app
from database import db, User
from extensions import limiter

flask_app.config["TESTING"] = True
# Flask-Limiter reads RATELIMIT_ENABLED once at init_app() time and caches it
# on the instance, so setting app.config here (after create_app() already
# ran) has no effect — set the instance attribute directly instead.
limiter.enabled = False


@pytest.fixture(autouse=True)
def _reset_detector_registry(tmp_path):
    """detector._registry is a process-wide singleton keyed by sensor_type,
    and FaultDetector.__init__ loads any model already saved under
    detector.MODEL_DIR — so without resetting both, training a model in one
    test leaks into every other test that touches the same sensor_type.
    Give each test its own empty registry and model directory."""
    import detector
    detector._registry.clear()
    original_model_dir = detector.MODEL_DIR
    detector.MODEL_DIR = str(tmp_path)
    yield
    detector.MODEL_DIR = original_model_dir
    detector._registry.clear()


@pytest.fixture()
def client():
    with flask_app.test_client() as c:
        yield c


_user_counter = iter(range(1, 100_000))


@pytest.fixture()
def auth_token(client):
    """Register a fresh, uniquely-named user and return auth headers.

    The whole test session shares one database (see _TEST_DB_PATH above), so
    each call needs a distinct username/email rather than a fixed one.
    """
    n = next(_user_counter)
    resp = client.post("/auth/register", json={
        "username": f"test_operator_{n}",
        "email": f"test_operator_{n}@example.com",
        "password": "testpass123",
    })
    assert resp.status_code == 201, resp.get_json()
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin_token(client):
    """A user with the 'admin' role — registration can never grant this (by
    design, see test_register_cannot_grant_admin_role), so tests that need to
    set up data as a privileged user promote one directly in the database,
    the way a real admin would via `python` shell / direct DB access, not
    through the API."""
    n = next(_user_counter)
    username = f"test_admin_{n}"
    reg = client.post("/auth/register", json={
        "username": username,
        "email": f"test_admin_{n}@example.com",
        "password": "testpass123",
    })
    assert reg.status_code == 201, reg.get_json()
    user_id = reg.get_json()["user"]["id"]

    with flask_app.app_context():
        user = db.session.get(User, user_id)
        user.role = "admin"
        db.session.commit()

    token = create_access_token(identity=str(user_id))
    return {"Authorization": f"Bearer {token}"}
