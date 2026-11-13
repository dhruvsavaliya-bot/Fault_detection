"""
mailer.py — minimal outbound email, with a console fallback.

If SMTP_HOST is configured (see backend/.env.example), sends real email via
smtplib. Otherwise, logs the message instead of sending it — so password
reset and email verification work out of the box in local/team-internal use
without anyone having to stand up mail infrastructure first. Configure real
SMTP before relying on this for a deployment where recipients can't just
read the server's own logs.
"""

import os
import logging
import smtplib
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def send_email(to_email: str, subject: str, body: str) -> bool:
    host = os.getenv("SMTP_HOST")

    if not host:
        logger.warning(
            "SMTP_HOST not set — email not actually sent, logging it instead.\n"
            f"To: {to_email}\nSubject: {subject}\n{body}"
        )
        return False

    port      = int(os.getenv("SMTP_PORT", 587))
    user      = os.getenv("SMTP_USER")
    password  = os.getenv("SMTP_PASS")
    from_addr = os.getenv("SMTP_FROM", user or "no-reply@faultsense.local")

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"]    = from_addr
    msg["To"]      = to_email

    try:
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.starttls()
            if user and password:
                server.login(user, password)
            server.sendmail(from_addr, [to_email], msg.as_string())
        return True
    except (smtplib.SMTPException, OSError) as e:
        # A broken SMTP config (wrong password, blocked port, etc.) should
        # never break registration/password-reset for the person using the
        # app — log it loudly, including the link, so it's still recoverable.
        logger.error(
            f"SMTP send failed ({e}) — falling back to logging the email.\n"
            f"To: {to_email}\nSubject: {subject}\n{body}"
        )
        return False
