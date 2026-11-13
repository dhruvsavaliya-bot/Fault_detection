"""
extensions.py — Shared Flask extension instances.

Kept separate from app.py so route modules can import them directly
(`from extensions import socketio`) without a circular import back to
app.py, which is what registers the blueprints that live in those modules.
"""

from flask_socketio import SocketIO
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

socketio = SocketIO(
    cors_allowed_origins="*",
    async_mode="threading"
)

limiter = Limiter(key_func=get_remote_address)
