import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.email import EmailError, EmailMessage, get_email_sender
from app.core.email_templates import newsletter_email
from app.database import get_db
from app.dependencies import get_current_admin
from app.models import Lead, NewsletterIssue, User
from app.schemas import NewsletterResult, NewsletterSend

logger = logging.getLogger("app.newsletter")
router = APIRouter(prefix="/api/newsletter", tags=["newsletter"])
settings = get_settings()


def _unsubscribe_url(token: str) -> str:
    return f"{settings.public_api_url.rstrip('/')}/api/newsletter/unsubscribe?token={token}"


@router.post("/send", response_model=NewsletterResult)
def send_newsletter(
    payload: NewsletterSend,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> NewsletterResult:
    sender = get_email_sender()

    if payload.test_to:
        html, text = newsletter_email(
            payload.subject, payload.body_markdown, _unsubscribe_url("preview-token")
        )
        try:
            sender.send(
                EmailMessage(
                    to=payload.test_to, subject=f"[TEST] {payload.subject}", html=html, text=text
                )
            )
        except EmailError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
            ) from exc
        logger.info("newsletter_test_sent", extra={"to": payload.test_to})
        return NewsletterResult(
            subject=payload.subject,
            audience=payload.audience,
            recipient_count=1,
            failed_count=0,
            test=True,
        )

    stmt = select(Lead).where(Lead.newsletter_opt_in.is_(True))
    if payload.audience != "all":
        stmt = stmt.where(Lead.role == payload.audience)
    recipients = db.execute(stmt).scalars().all()

    if not recipients:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No opted-in subscribers match that audience.",
        )

    sent = failed = 0
    with sender.connection() as conn:
        for lead in recipients:
            unsubscribe = _unsubscribe_url(lead.unsubscribe_token)
            html, text = newsletter_email(payload.subject, payload.body_markdown, unsubscribe)
            try:
                conn.send(
                    EmailMessage(
                        to=lead.email,
                        subject=payload.subject,
                        html=html,
                        text=text,
                        list_unsubscribe=unsubscribe,
                    )
                )
                sent += 1
            except EmailError as exc:
                failed += 1
                logger.error(
                    "newsletter_send_failed", extra={"lead_id": lead.id, "error": str(exc)}
                )
            # Gentle pacing keeps shared SMTP hosts from rate-limiting the batch.
            if settings.newsletter_batch_pause_seconds:
                time.sleep(settings.newsletter_batch_pause_seconds)

    issue = NewsletterIssue(
        subject=payload.subject,
        body_markdown=payload.body_markdown,
        audience=payload.audience,
        recipient_count=sent,
        failed_count=failed,
        sent_by_id=admin.id,
    )
    db.add(issue)
    db.commit()

    logger.info(
        "newsletter_sent",
        extra={"subject": payload.subject, "sent": sent, "failed": failed},
    )
    return NewsletterResult(
        subject=payload.subject,
        audience=payload.audience,
        recipient_count=sent,
        failed_count=failed,
    )


@router.get("/unsubscribe")
def unsubscribe(token: str = Query(min_length=8), db: Session = Depends(get_db)) -> Response:
    """One-click unsubscribe. Must stay a GET so it works straight from an email."""
    lead = db.query(Lead).filter(Lead.unsubscribe_token == token).first()

    if lead is not None and lead.newsletter_opt_in:
        lead.newsletter_opt_in = False
        db.commit()
        logger.info("newsletter_unsubscribed", extra={"lead_id": lead.id})

    # Always render the same page: a wrong token must not reveal whether it exists.
    page = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Unsubscribed - SocioTurtle</title></head>
<body style="font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
background:#f6f7fb;color:#16192a;display:flex;align-items:center;
justify-content:center;min-height:100vh;margin:0;">
<div style="background:#fff;border:1px solid #dfe3ec;border-radius:10px;
padding:32px;max-width:420px;text-align:center;">
<h1 style="font-size:20px;margin:0 0 10px;">You are unsubscribed</h1>
<p style="color:#6b7284;line-height:1.6;margin:0;">
You will no longer receive the SocioTurtle newsletter.
You can register again any time on socioturtle.com.</p>
</div></body></html>"""
    return Response(content=page, media_type="text/html")


@router.post("/unsubscribe")
def unsubscribe_one_click(
    token: str = Query(min_length=8), db: Session = Depends(get_db)
) -> Response:
    """RFC 8058 endpoint that Gmail and Outlook call from their own UI."""
    unsubscribe(token=token, db=db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
