"""
authz.py — role-based access control.

FaultSense is a shared tool: everyone on the team sees the same sensors,
faults, and alerts (there's no per-user data isolation, by design — see
README.md). What roles *do* gate is who can reconfigure the monitoring setup
itself:

  - operator (default for self-registration): day-to-day use — view
    everything, submit readings, resolve faults, manage alerts.
  - engineer: operator + can add sensors and train detection models.
  - admin: engineer + can delete sensors.
"""

from functools import wraps
from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from database import db, User


def require_role(*roles):
    """Like @jwt_required(), but also rejects users whose role isn't in
    `roles`. Use instead of (not in addition to) @jwt_required()."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user = db.session.get(User, int(get_jwt_identity()))
            if not user or user.role not in roles:
                return jsonify({"error": "This action requires a higher role"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator
