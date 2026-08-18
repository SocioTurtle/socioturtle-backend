"""Email-address verification via a one-time 6-digit code.

Mirrors the captcha module's shape: a hashed, TTL-bound, single-purpose
secret. Unlike captcha, a wrong guess doesn't burn the code immediately —
`attempts` caps retries instead, since humans mistype codes more often than
they mistype a captcha they can see rendered right in front of them.
"""

import hashlib
import logging
import secrets
import string
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import LeadOtp

logger = logging.getLogger("app.otp")


class OtpError(Exception):
    pass


def _hash(code: str) -> str:
    return hashlib.sha256(code.strip().encode()).hexdigest()


def _generate_code() -> str:
    return "".join(secrets.choice(string.digits) for _ in range(6))


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def issue(db: Session, email: str) -> tuple[str, int]:
    """Create a code for `email`. Returns (plaintext code, ttl seconds).

    Raises OtpError if a code was requested for this address too recently.
    """
    settings = get_settings()
    email = email.strip().lower()

    # Only an unredeemed code counts against the cooldown: once a code has been
    # fully used to complete a registration, that cycle is over and a fresh
    # request is a new legitimate attempt, not someone hammering the inbox.
    recent = (
        db.query(LeadOtp)
        .filter(LeadOtp.email == email, LeadOtp.redeemed.is_(False))
        .order_by(LeadOtp.created_at.desc())
        .first()
    )
    if recent is not None:
        age = (datetime.now(timezone.utc) - _aware(recent.created_at)).total_seconds()
        if age < settings.otp_resend_cooldown_seconds:
            wait = int(settings.otp_resend_cooldown_seconds - age)
            raise OtpError(f"Please wait {wait}s before requesting another code.")

    code = _generate_code()
    otp = LeadOtp(
        id=str(uuid.uuid4()),
        email=email,
        code_hash=_hash(code),
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=settings.otp_ttl_seconds),
    )
    db.add(otp)
    _purge_expired(db, email)
    db.commit()

    logger.info("otp_issued", extra={"email": email})
    return code, settings.otp_ttl_seconds


def verify(db: Session, email: str, code: str) -> str:
    """Check `code` against the newest unverified code for `email`.

    Returns a verify_token to pass to `redeem()` at registration time.
    """
    settings = get_settings()
    email = email.strip().lower()

    otp = (
        db.query(LeadOtp)
        .filter(LeadOtp.email == email, LeadOtp.verified.is_(False))
        .order_by(LeadOtp.created_at.desc())
        .first()
    )
    if otp is None:
        raise OtpError("Request a new code first.")
    if otp.attempts >= settings.otp_max_attempts:
        raise OtpError("Too many attempts. Request a new code.")
    if _aware(otp.expires_at) < datetime.now(timezone.utc):
        raise OtpError("Code expired. Request a new one.")

    otp.attempts += 1
    if not secrets.compare_digest(otp.code_hash, _hash(code)):
        db.commit()
        raise OtpError("Incorrect code.")

    otp.verified = True
    otp.verify_token = secrets.token_urlsafe(32)
    db.commit()
    logger.info("otp_verified", extra={"email": email})
    return otp.verify_token


def redeem(db: Session, email: str, verify_token: str) -> None:
    """Called by lead registration to confirm the email was actually verified.

    Raises OtpError if the token is missing, doesn't match, is stale, or has
    already been used for a previous registration.
    """
    settings = get_settings()
    email = email.strip().lower()

    otp = (
        db.query(LeadOtp)
        .filter(
            LeadOtp.email == email,
            LeadOtp.verify_token == verify_token,
            LeadOtp.verified.is_(True),
        )
        .order_by(LeadOtp.created_at.desc())
        .first()
    )
    if otp is None:
        raise OtpError("Please verify your email before registering.")
    if otp.redeemed:
        raise OtpError("This verification has already been used. Please verify again.")

    verified_deadline = _aware(otp.expires_at) + timedelta(
        minutes=settings.otp_verified_window_minutes
    )
    if verified_deadline < datetime.now(timezone.utc):
        raise OtpError("Verification expired. Please verify your email again.")

    otp.redeemed = True
    db.commit()


def _purge_expired(db: Session, email: str) -> None:
    db.query(LeadOtp).filter(
        LeadOtp.email == email,
        LeadOtp.expires_at < datetime.now(timezone.utc),
    ).delete(synchronize_session=False)
