"""Pluggable captcha verification.

`local` renders a self-contained SVG challenge with no third-party dependency, so
the MVP runs offline. `hcaptcha` swaps in a hosted provider without touching the
routers -- both satisfy the same two-call contract (issue, verify).
"""

import base64
import hashlib
import logging
import random
import secrets
import string
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from xml.sax.saxutils import escape

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import CaptchaChallenge
from app.schemas import CaptchaAnswer, CaptchaChallengeOut

logger = logging.getLogger("app.captcha")

_ALPHABET = "".join(c for c in string.ascii_uppercase + string.digits if c not in "OI01")


class CaptchaError(Exception):
    pass


class CaptchaProvider(ABC):
    @abstractmethod
    def issue(self, db: Session) -> CaptchaChallengeOut: ...

    @abstractmethod
    def verify(self, db: Session, answer: CaptchaAnswer) -> None:
        """Raise CaptchaError if the challenge is wrong, expired, or reused."""


def _hash(value: str) -> str:
    return hashlib.sha256(value.strip().upper().encode()).hexdigest()


def _render_svg(text: str) -> str:
    rng = random.SystemRandom()
    width, height = 220, 70
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="captcha">',
        f'<rect width="{width}" height="{height}" fill="#f2f4f7"/>',
    ]
    for _ in range(6):
        x1, y1, x2, y2 = (
            rng.randint(0, width),
            rng.randint(0, height),
            rng.randint(0, width),
            rng.randint(0, height),
        )
        parts.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#c3c9d4" stroke-width="1"/>'
        )
    for i, char in enumerate(text):
        x = 24 + i * 36
        y = rng.randint(46, 54)
        rotate = rng.randint(-28, 28)
        fill = f"hsl({rng.randint(200, 280)}, 55%, 35%)"
        parts.append(
            f'<text x="{x}" y="{y}" font-family="monospace" font-size="34" font-weight="700" '
            f'fill="{fill}" transform="rotate({rotate} {x} {y})">{escape(char)}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


class LocalCaptchaProvider(CaptchaProvider):
    def __init__(self, ttl_seconds: int, length: int = 5) -> None:
        self.ttl_seconds = ttl_seconds
        self.length = length

    def issue(self, db: Session) -> CaptchaChallengeOut:
        text = "".join(secrets.choice(_ALPHABET) for _ in range(self.length))
        challenge = CaptchaChallenge(
            id=str(uuid.uuid4()),
            answer_hash=_hash(text),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=self.ttl_seconds),
        )
        db.add(challenge)
        self._purge_expired(db)
        db.commit()
        logger.info("captcha_issued", extra={"challenge_id": challenge.id})
        svg = _render_svg(text)
        data_uri = "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
        return CaptchaChallengeOut(
            challenge_id=challenge.id,
            image_data_uri=data_uri,
            expires_in=self.ttl_seconds,
        )

    def verify(self, db: Session, answer: CaptchaAnswer) -> None:
        challenge = db.get(CaptchaChallenge, answer.challenge_id)
        if challenge is None:
            raise CaptchaError("Captcha challenge not found.")

        already_consumed = challenge.consumed
        expires_at = challenge.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        # Burn the challenge on any verification attempt so a wrong answer cannot
        # be brute-forced against the same image.
        challenge.consumed = True
        db.commit()

        if already_consumed:
            raise CaptchaError("Captcha already used.")
        if expires_at < datetime.now(timezone.utc):
            raise CaptchaError("Captcha expired.")
        if not secrets.compare_digest(challenge.answer_hash, _hash(answer.answer)):
            raise CaptchaError("Incorrect captcha.")

    def _purge_expired(self, db: Session) -> None:
        db.query(CaptchaChallenge).filter(
            CaptchaChallenge.expires_at < datetime.now(timezone.utc)
        ).delete(synchronize_session=False)


class HCaptchaProvider(CaptchaProvider):
    VERIFY_URL = "https://api.hcaptcha.com/siteverify"

    def __init__(self, secret: str) -> None:
        if not secret:
            raise ValueError("HCAPTCHA_SECRET must be set when CAPTCHA_PROVIDER=hcaptcha")
        self.secret = secret

    def issue(self, db: Session) -> CaptchaChallengeOut:
        raise CaptchaError("hCaptcha challenges are rendered by the client widget.")

    def verify(self, db: Session, answer: CaptchaAnswer) -> None:
        try:
            response = httpx.post(
                self.VERIFY_URL,
                data={"secret": self.secret, "response": answer.answer},
                timeout=10,
            )
            response.raise_for_status()
            body = response.json()
        except httpx.HTTPError as exc:
            logger.error("hcaptcha_unreachable", extra={"error": str(exc)})
            raise CaptchaError("Captcha service unavailable.") from exc

        if not body.get("success"):
            raise CaptchaError("Incorrect captcha.")


def build_captcha_provider() -> CaptchaProvider:
    settings = get_settings()
    if settings.captcha_provider == "hcaptcha":
        return HCaptchaProvider(settings.hcaptcha_secret)
    return LocalCaptchaProvider(settings.captcha_ttl_seconds)


_provider: CaptchaProvider | None = None


def get_captcha_provider() -> CaptchaProvider:
    global _provider
    if _provider is None:
        _provider = build_captcha_provider()
    return _provider
