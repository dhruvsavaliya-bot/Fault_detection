"""
app.py — Flask entry point for Fault Detection System
"""

from flask import Flask, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO
from flask_jwt_extended import JWTManager
import os
import logging

from database import db, init_db
from routes.api import api_bp
from routes.auth import auth_bp
from routes.reports import reports_bp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

logger = logging.getLogger(__name__)

socketio = SocketIO(
    cors_allowed_origins="*",
    async_mode="threading"
)


def create_app():

    # BASE DIRECTORY
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    # FRONTEND DIRECTORY
    FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")

    print("Frontend Path:", FRONTEND_DIR)

    app = Flask(__name__)

    # CONFIG
    app.config["SECRET_KEY"] = os.getenv(
        "SECRET_KEY",
        "fd-secret-key-2024"
    )

    app.config["JWT_SECRET_KEY"] = os.getenv(
        "JWT_SECRET",
        "fd-jwt-secret-2024"
    )

    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL",
        "sqlite:///fault_detection.db"
    )

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = 86400

    # ENABLE CORS
    CORS(app, origins="*")

    # INIT EXTENSIONS
    db.init_app(app)
    socketio.init_app(app)
    JWTManager(app)

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

    port = int(os.getenv("PORT", 5000))

    logger.info(
        f"Server running → http://localhost:{port}"
    )

    socketio.run(
        app,
        host="0.0.0.0",
        port=port,
        debug=True
    )