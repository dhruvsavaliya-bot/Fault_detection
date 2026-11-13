"""
routes/auth.py — Authentication endpoints (register, login, logout,
email verification, password reset)
"""

import re
import secrets
import hashlib
from datetime import timedelta
from flask import Blueprint, request, jsonify, redirect
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from database import db, User, EmailVerification, PasswordResetToken, utcnow
from extensions import limiter
from mailer import send_email

auth_bp = Blueprint("auth", __name__)

EMAIL_RE    = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.\- ]{3,80}$")
MIN_PASSWORD_LEN = 6

EMAIL_VERIFICATION_TTL = timedelta(hours=24)
PASSWORD_RESET_TTL     = timedelta(hours=1)


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def _send_verification_email(user, base_url):
    raw_token = secrets.token_urlsafe(32)
    record = EmailVerification(
        user_id    = user.id,
        token_hash = _hash_token(raw_token),
        expires_at = utcnow() + EMAIL_VERIFICATION_TTL,
    )
    db.session.add(record)
    db.session.commit()

    link = f"{base_url}/auth/verify-email?token={raw_token}"
    send_email(
        user.email,
        "Verify your FaultSense account",
        f"Hi {user.username},\n\nConfirm your email address:\n{link}\n\n"
        f"This link expires in 24 hours.",
    )


@auth_bp.route("/register", methods=["POST"])
@limiter.limit("10 per minute")
def register():
    data = request.get_json(silent=True) or {}
    required = ["username", "email", "password"]
    if not all(data.get(k) for k in required):
        return jsonify({"error": "Missing fields"}), 400

    username = data["username"].strip()
    email    = data["email"].strip()
    password = data["password"]

    if not USERNAME_RE.match(username):
        return jsonify({"error": "Username must be 3-80 characters (letters, numbers, spaces, . _ -)"}), 400
    if not EMAIL_RE.match(email):
        return jsonify({"error": "Enter a valid email address"}), 400
    if len(password) < MIN_PASSWORD_LEN:
        return jsonify({"error": f"Password must be at least {MIN_PASSWORD_LEN} characters"}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already taken"}), 409
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 409

    user = User(
        username      = username,
        email         = email,
        password_hash = generate_password_hash(password),
        role          = "operator",  # self-registration can never grant elevated roles
    )
    db.session.add(user)
    db.session.commit()

    _send_verification_email(user, request.host_url.rstrip("/"))

    token = create_access_token(identity=str(user.id))
    return jsonify({"token": token, "user": user.to_dict()}), 201


@auth_bp.route("/login", methods=["POST"])
@limiter.limit("15 per minute")
def login():
    data = request.get_json(silent=True) or {}
    login_id = data.get("username", "").strip()
    password = data.get("password", "")

    if not login_id or not password:
        return jsonify({"error": "Missing username or password"}), 400

    if "@" in login_id:
        user = User.query.filter_by(email=login_id).first()
    else:
        user = User.query.filter_by(username=login_id).first()

    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Invalid credentials"}), 401
    if not user.is_active:
        return jsonify({"error": "Account disabled"}), 403

    token = create_access_token(identity=str(user.id))
    return jsonify({"token": token, "user": user.to_dict()}), 200


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    user_id = int(get_jwt_identity())
    user    = User.query.get_or_404(user_id)
    return jsonify(user.to_dict()), 200


@auth_bp.route("/change-password", methods=["PUT"])
@jwt_required()
def change_password():
    user_id = int(get_jwt_identity())
    user    = User.query.get_or_404(user_id)
    data    = request.get_json(silent=True) or {}
    new_password = data.get("new_password", "")

    if not check_password_hash(user.password_hash, data.get("old_password", "")):
        return jsonify({"error": "Wrong current password"}), 403
    if len(new_password) < MIN_PASSWORD_LEN:
        return jsonify({"error": f"Password must be at least {MIN_PASSWORD_LEN} characters"}), 400

    user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    return jsonify({"message": "Password updated"}), 200


# ── Email verification ───────────────────────────────────────────────────────
@auth_bp.route("/resend-verification", methods=["POST"])
@jwt_required()
@limiter.limit("5 per hour")
def resend_verification():
    user_id = int(get_jwt_identity())
    user    = User.query.get_or_404(user_id)
    if user.is_verified:
        return jsonify({"message": "Already verified"}), 200

    # replace any existing pending record rather than piling up rows
    EmailVerification.query.filter_by(user_id=user.id).delete()
    db.session.commit()
    _send_verification_email(user, request.host_url.rstrip("/"))
    return jsonify({"message": "Verification email sent"}), 200


@auth_bp.route("/verify-email", methods=["GET"])
def verify_email():
    raw_token = request.args.get("token", "")
    record = EmailVerification.query.filter_by(token_hash=_hash_token(raw_token)).first()

    if not record or record.expires_at < utcnow():
        return redirect("/login.html?verify=expired")
    if record.verified_at is not None:
        return redirect("/login.html?verify=already")

    record.verified_at = utcnow()
    db.session.commit()
    return redirect("/login.html?verify=success")


# ── Password reset ───────────────────────────────────────────────────────────
@auth_bp.route("/forgot-password", methods=["POST"])
@limiter.limit("5 per hour")
def forgot_password():
    data  = request.get_json(silent=True) or {}
    email = data.get("email", "").strip()

    # Always the same response whether or not the email matched — a
    # different message would let someone enumerate registered accounts.
    generic_response = jsonify({
        "message": "If an account exists for that email, a reset link has been sent."
    }), 200

    if not email:
        return generic_response

    user = User.query.filter_by(email=email).first()
    if not user:
        return generic_response

    raw_token = secrets.token_urlsafe(32)
    db.session.add(PasswordResetToken(
        user_id    = user.id,
        token_hash = _hash_token(raw_token),
        expires_at = utcnow() + PASSWORD_RESET_TTL,
    ))
    db.session.commit()

    link = f"{request.host_url.rstrip('/')}/reset-password.html?token={raw_token}"
    send_email(
        user.email,
        "Reset your FaultSense password",
        f"Hi {user.username},\n\nReset your password:\n{link}\n\n"
        f"This link expires in 1 hour. If you didn't request this, ignore this email.",
    )
    return generic_response


@auth_bp.route("/reset-password", methods=["POST"])
@limiter.limit("10 per hour")
def reset_password():
    data      = request.get_json(silent=True) or {}
    raw_token = data.get("token", "")
    new_password = data.get("new_password", "")

    if len(new_password) < MIN_PASSWORD_LEN:
        return jsonify({"error": f"Password must be at least {MIN_PASSWORD_LEN} characters"}), 400

    record = PasswordResetToken.query.filter_by(token_hash=_hash_token(raw_token)).first()
    if not record or record.used_at is not None or record.expires_at < utcnow():
        return jsonify({"error": "This reset link is invalid or has expired"}), 400

    user = User.query.get_or_404(record.user_id)
    user.password_hash = generate_password_hash(new_password)
    record.used_at = utcnow()
    db.session.commit()
    return jsonify({"message": "Password reset — log in with your new password"}), 200
