"""
app.py — Flask entry point for Fault Detection System
"""

import secrets
from flask import Flask, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from dotenv import load_dotenv
import os
import logging

from database import db, init_db
from extensions import socketio, limiter
from routes.api import api_bp
from routes.auth import auth_bp
from routes.reports import reports_bp

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

logger = logging.getLogger(__name__)


def _persisted_secret(base_dir, env_var, filename):
    """Read a secret from the environment, falling back to a locally
    generated and persisted one (so it's stable across restarts but never
    a guessable hardcoded constant checked into source control)."""
    value = os.getenv(env_var)
    if value:
        return value

    instance_dir = os.path.join(base_dir, "instance")
    os.makedirs(instance_dir, exist_ok=True)
    path = os.path.join(instance_dir, filename)

    if os.path.exists(path):
        with open(path, "r") as f:
            return f.read().strip()

    generated = secrets.token_hex(32)
    with open(path, "w") as f:
        f.write(generated)
    logger.warning(
        f"{env_var} not set — generated and persisted a local secret at "
        f"{path}. Set {env_var} explicitly for a real deployment."
    )
    return generated


def create_app():

    # BASE DIRECTORY
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    # FRONTEND DIRECTORY
    FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")

    app = Flask(__name__)

    # CONFIG
    app.config["SECRET_KEY"] = _persisted_secret(BASE_DIR, "SECRET_KEY", "secret.key")
    app.config["JWT_SECRET_KEY"] = _persisted_secret(BASE_DIR, "JWT_SECRET", "jwt_secret.key")

    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL",
        "sqlite:///fault_detection.db"
    )

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = 86400

    # ENABLE CORS
    CORS(app, origins=os.getenv("CORS_ORIGINS", "*"))

    # Rate-limit storage: in-memory by default (fine for a single process;
    # each worker would track its own limits independently under gunicorn
    # with >1 worker). Point RATELIMIT_STORAGE_URI at Redis for anything
    # beyond single-process local use, e.g. redis://localhost:6379
    app.config["RATELIMIT_STORAGE_URI"] = os.getenv("RATELIMIT_STORAGE_URI", "memory://")

    # INIT EXTENSIONS
    db.init_app(app)
    socketio.init_app(app)
    JWTManager(app)
    limiter.init_app(app)

    # REGISTER BLUEPRINTS
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(reports_bp, url_prefix="/reports")

    # HOME ROUTE
    @app.route("/")
    def home():
        return send_from_directory(FRONTEND_DIR, "login.html")

    # SERVE CSS FILES
    @app.route('/css/<path:filename>')
    def serve_css(filename):
        return send_from_directory(
            os.path.join(FRONTEND_DIR, 'css'),
            filename
        )

    # SERVE JS FILES
    @app.route('/js/<path:filename>')
    def serve_js(filename):
        return send_from_directory(
            os.path.join(FRONTEND_DIR, 'js'),
            filename
        )

    # SERVE HTML FILES / FRONTEND ROUTES
    @app.route('/<path:path>')
    def serve_frontend(path):

        file_path = os.path.join(FRONTEND_DIR, path)

        # IF FILE EXISTS
        if os.path.isfile(file_path):
            return send_from_directory(FRONTEND_DIR, path)

        # OTHERWISE LOAD LOGIN PAGE
        return send_from_directory(FRONTEND_DIR, "login.html")

    # INIT DATABASE
    with app.app_context():
        init_db()
        logger.info("DB ready")

    return app


app = create_app()


@socketio.on("connect")
def on_connect():
    logger.info("WebSocket client connected")


@socketio.on("disconnect")
def on_disconnect():
    logger.info("WebSocket client disconnected")


if __name__ == "__main__":

    port  = int(os.getenv("PORT", 5000))
    # Defaults OFF: debug=True exposes Werkzeug's interactive debugger, which
    # lets anyone who triggers an unhandled exception execute arbitrary code
    # in the browser. Opt in explicitly for local development.
    debug = os.getenv("FLASK_DEBUG", "false").lower() in ("1", "true", "yes")

    logger.info(
        f"Server running → http://localhost:{port} (debug={debug})"
    )

    socketio.run(
        app,
        host="0.0.0.0",
        port=port,
        debug=debug,
        use_reloader=False,  # the stat-based reloader can hang when the
                             # project sits inside a OneDrive/Dropbox-synced
                             # directory; restart manually after edits.
    )
