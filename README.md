# FaultSense

Industrial fault detection: a Flask + Socket.IO backend that watches sensor
readings (temperature, vibration, pressure, current, voltage, humidity)
through three detection strategies — hard rule thresholds, rolling z-score
deviation, and a trainable Isolation Forest model — and a vanilla HTML/CSS/JS
dashboard that shows faults, alerts, and reports in real time.

## Architecture

```
backend/
  app.py            — Flask app factory, config, static file serving
  extensions.py     — shared SocketIO / rate-limiter instances
  database.py       — SQLAlchemy models (User, Sensor, SensorReading, Fault, Alert)
  detector.py       — the detection engine (rule-based + statistical + ML)
  routes/
    auth.py         — register / login / change-password
    api.py          — sensors, readings, faults, alerts, dashboard summary, training
    reports.py      — analytics + CSV export
  tests/            — pytest suite (auth, sensors, faults, detector — run in isolation
                       from the real database and model files)
frontend/
  *.html, css/, js/ — static dashboard, served directly by Flask
```

The frontend talks to the backend purely over the REST API in `js/api.js` and
a Socket.IO connection for live fault push notifications — there's no build
step, bundler, or framework.

## Running locally

```bash
cd backend
python -m venv venv          # see the note below if this project sits in OneDrive/Dropbox
venv/Scripts/activate         # or: source venv/bin/activate on macOS/Linux
pip install -r requirements.txt
python app.py
```

Then open **http://localhost:5000**. The database seeds itself on first run
(6 demo sensors, an `admin`/`admin123` account) if it doesn't already exist at
`backend/instance/fault_detection.db`.

> **If this repo lives inside a OneDrive/Dropbox/Google Drive synced folder**,
> create the virtualenv *outside* that synced tree instead (e.g.
> `C:\Users\you\venvs\faultsense-backend`) and point your IDE/shell at that
> interpreter. Real-time cloud sync racing with pip's rapid writes to
> `site-packages` while installing numpy/pandas/scikit-learn can corrupt the
> install (duplicate `.dist-info` folders, `ImportError`s on first run) and
> can make `venv/` briefly undeletable. This is a sync-tool problem, not a
> project one — it doesn't happen on a local-disk path.

### Environment variables

See `backend/.env.example`. Nothing is required for local development —
`SECRET_KEY`/`JWT_SECRET` are auto-generated and persisted to
`backend/instance/*.key` (gitignored) on first run if unset. Set them
explicitly, and point `DATABASE_URL` at Postgres/MySQL, for any real
deployment.

### Running with Docker

```bash
cp backend/.env.example .env   # fill in SECRET_KEY / JWT_SECRET
docker compose up --build
```

## Tests

```bash
cd backend
pip install -r requirements.txt   # includes pytest
pytest tests/ -v
```

Tests run against an isolated temp-file SQLite database and a temp model
directory — they never touch `backend/instance/fault_detection.db` or
`backend/models/`. CI runs the same suite on every push via
`.github/workflows/tests.yml`.

## Security notes

- Self-registration always creates an `operator` account — role escalation
  via the API is not possible.
- `/auth/login` and `/auth/register` are rate-limited per IP (in-memory
  storage by default; configure a Redis backend via Flask-Limiter's
  `storage_uri` for a multi-process deployment).
- Passwords require a minimum of 6 characters, enforced server-side (not just
  in the UI).
- `FLASK_DEBUG` defaults to `false`. Only set it `true` for local dev —
  Flask's debug mode runs an interactive in-browser Python console on any
  unhandled exception, which is a remote code execution hole if it's ever
  left on somewhere reachable by anyone other than you.

### Roles

FaultSense is a **shared team tool, not multi-tenant** — every logged-in user
sees the same sensors, faults, and alerts; there's no per-user or
per-organization data isolation. What roles gate is who can reconfigure the
monitoring setup itself (see `backend/authz.py`):

| Action                          | operator | engineer | admin |
|----------------------------------|:--------:|:--------:|:-----:|
| View sensors/faults/alerts/reports | ✓ | ✓ | ✓ |
| Submit readings, resolve faults, manage alerts | ✓ | ✓ | ✓ |
| Add a sensor, train a model      |          | ✓ | ✓ |
| Delete a sensor                  |          |          | ✓ |

Self-registration always creates an `operator`. Promote a user to
`engineer`/`admin` directly in the database — there's no admin UI for this
yet (`sqlite3 backend/instance/fault_detection.db "UPDATE users SET role='admin' WHERE username='you';"`).

## Known limitations / possible next steps

- SQLite is fine for this scale; a real multi-user deployment should move to
  Postgres (`DATABASE_URL`) and add schema migrations (Alembic/Flask-Migrate
  — there are none today, just `db.create_all()`).
- The Isolation Forest model is trained and shared per **sensor type**, not
  per individual sensor — two sensors of the same type with very different
  normal operating ranges share one model. This mirrors the current product
  design (Settings page trains "a sensor type"); switching to per-sensor
  models would be a larger, deliberate change.
- `detector.py`'s per-process model registry (`_registry`) means each
  gunicorn/uWSGI worker in a multi-worker deployment would hold its own
  independent copy — fine for a single process, not for horizontal scaling.
- The dev server (`python app.py`) is what `Dockerfile` runs too; a
  higher-throughput deployment should sit behind a real WSGI/ASGI server
  (gunicorn with eventlet/gevent workers, to match Flask-SocketIO's async
  requirements).
- No CSRF protection beyond JWT-in-header (fine for an API-only, non-cookie
  auth flow like this one; relevant only if cookie-based auth is ever added).
