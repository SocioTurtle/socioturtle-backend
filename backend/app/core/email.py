"""Email delivery.

`console` writes messages to the log so the whole invite/newsletter flow can be
exercised without credentials or a live mail server. `smtp` talks to Gmail,
Zoho, or any other SMTP host directly over port 25/465/587 — which many PaaS
free tiers block outbound to prevent spam abuse. `resend` instead calls the
Resend HTTP API over HTTPS (port 443), which sidesteps that entirely. All
three satisfy the same interface, so nothing upstream changes when you switch.
"""

import logging
import smtplib
import ssl
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass
from email.message import EmailMessage as MimeMessage
from email.utils import formataddr
from typing import Iterator

import httpx

from app.config import get_settings

logger = logging.getLogger("app.email")


class EmailError(Exception):
    pass


@dataclass(slots=True)
class EmailMessage:
    to: str
    subject: str
    html: str
    text: str
    # RFC 8058 one-click unsubscribe; keeps bulk mail out of spam folders.
    list_unsubscribe: str | None = None


class EmailSender(ABC):
    @abstractmethod
    @contextmanager
    def connection(self) -> Iterator["EmailSender"]:
        """Reuse one transport for a batch instead of reconnecting per message."""

    @abstractmethod
    def send(self, message: EmailMessage) -> None:
        """Deliver one message, or raise EmailError."""


def _build_mime(message: EmailMessage) -> MimeMessage:
    settings = get_settings()
    mime = MimeMessage()
    mime["Subject"] = message.subject
    mime["From"] = formataddr((settings.email_from_name, settings.email_from))
    mime["To"] = message.to
    if settings.email_reply_to:
        mime["Reply-To"] = settings.email_reply_to
    if message.list_unsubscribe:
        mime["List-Unsubscribe"] = f"<{message.list_unsubscribe}>"
        mime["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    mime.set_content(message.text)
    mime.add_alternative(message.html, subtype="html")
    return mime


class ConsoleEmailSender(EmailSender):
    @contextmanager
    def connection(self) -> Iterator[EmailSender]:
        yield self

    def send(self, message: EmailMessage) -> None:
        logger.info(
            "email_console",
            extra={
                "to": message.to,
                "subject": message.subject,
                "body_preview": message.text[:400],
            },
        )


class SmtpEmailSender(EmailSender):
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.smtp_host:
            raise ValueError("SMTP_HOST must be set when EMAIL_BACKEND=smtp")
        self.host = settings.smtp_host
        self.port = settings.smtp_port
        self.user = settings.smtp_user
        self.password = settings.smtp_password
        self.use_tls = settings.smtp_use_tls
        self.use_ssl = settings.smtp_use_ssl
        self._client: smtplib.SMTP | None = None

    @contextmanager
    def connection(self) -> Iterator[EmailSender]:
        client = self._connect()
        self._client = client
        try:
            yield self
        finally:
            self._client = None
            try:
                client.quit()
            except smtplib.SMTPException:
                pass

    def _connect(self) -> smtplib.SMTP:
        try:
            if self.use_ssl:
                client: smtplib.SMTP = smtplib.SMTP_SSL(
                    self.host, self.port, context=ssl.create_default_context(), timeout=30
                )
            else:
                client = smtplib.SMTP(self.host, self.port, timeout=30)
                if self.use_tls:
                    client.starttls(context=ssl.create_default_context())
            if self.user:
                client.login(self.user, self.password)
            return client
        except (smtplib.SMTPException, OSError) as exc:
            raise EmailError(f"SMTP connection failed: {exc}") from exc

    def send(self, message: EmailMessage) -> None:
        mime = _build_mime(message)
        try:
            if self._client is not None:
                self._client.send_message(mime)
            else:
                with self.connection():
                    assert self._client is not None
                    self._client.send_message(mime)
        except (smtplib.SMTPException, OSError) as exc:
            raise EmailError(f"Could not send to {message.to}: {exc}") from exc


class ResendEmailSender(EmailSender):
    """Sends via the Resend HTTP API — no SMTP port involved."""

    API_URL = "https://api.resend.com/emails"

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.resend_api_key:
            raise ValueError("RESEND_API_KEY must be set when EMAIL_BACKEND=resend")
        self.api_key = settings.resend_api_key

    @contextmanager
    def connection(self) -> Iterator[EmailSender]:
        # Stateless HTTPS requests — nothing to keep open between messages.
        yield self

    def send(self, message: EmailMessage) -> None:
        settings = get_settings()
        payload: dict = {
            "from": formataddr((settings.email_from_name, settings.email_from)),
            "to": [message.to],
            "subject": message.subject,
            "html": message.html,
            "text": message.text,
        }
        if message.list_unsubscribe:
            payload["headers"] = {
                "List-Unsubscribe": f"<{message.list_unsubscribe}>",
                "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
            }
        try:
            response = httpx.post(
                self.API_URL,
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=15,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise EmailError(f"Could not send to {message.to}: {exc}") from exc


_sender: EmailSender | None = None


def get_email_sender() -> EmailSender:
    global _sender
    if _sender is None:
        settings = get_settings()
        if settings.email_backend == "smtp":
            _sender = SmtpEmailSender()
        elif settings.email_backend == "resend":
            _sender = ResendEmailSender()
        else:
            _sender = ConsoleEmailSender()
        logger.info("email_backend_selected", extra={"backend": settings.email_backend})
    return _sender


def reset_email_sender() -> None:
    """Test hook — forces the backend to be re-read from settings."""
    global _sender
    _sender = None
