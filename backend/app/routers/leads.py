import csv
import io
import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core import otp as otp_module
from app.core.email import EmailError, EmailMessage, get_email_sender
from app.core.email_templates import invite_email, newsletter_email, otp_email
from app.core.otp import OtpError
from app.database import get_db
from app.dependencies import get_current_admin
from app.models import Lead, NewsletterIssue, User
from app.schemas import (
    InviteRequest,
    InviteResult,
    LeadAccepted,
    LeadCreate,
    LeadList,
    LeadOut,
    OtpSendRequest,
    OtpSendResult,
    OtpVerifyRequest,
    OtpVerifyResult,
)

logger = logging.getLogger("app.leads")
router = APIRouter(prefix="/api/leads", tags=["leads"])
settings = get_settings()


def _hash_token(raw: str) -> str:
    import hashlib

    return hashlib.sha256(raw.encode()).hexdigest()


def _mint_and_send_invite(db: Session, lead: Lead, sender=None) -> bool:
    """Mint a one-time activation token for `lead` and email it.

    Returns True on send success, False on skip/failure. Never raises — the
    caller decides whether a failure should be fatal (send_invites, which
    reports it back to the admin) or swallowed (auto-invite on registration).
    """
    if lead.role == "employer":
        return False  # Employers are a contact list, not portal users
    if lead.status == "activated":
        return False

    now = datetime.now(timezone.utc)
    raw_token = secrets.token_urlsafe(32)
    lead.invite_token_hash = _hash_token(raw_token)
    lead.invite_expires_at = now + timedelta(hours=settings.invite_ttl_hours)

    activate_url = f"{settings.public_app_url.rstrip('/')}/?invite={raw_token}"
    html, text = invite_email(lead.name, lead.role, activate_url, settings.invite_ttl_hours)

    email_sender = sender or get_email_sender()
    try:
        email_sender.send(
            EmailMessage(to=lead.email, subject="Set up your SocioTurtle account", html=html, text=text)
        )
    except EmailError as exc:
        # Roll the token back so a failed send cannot leave a live link.
        lead.invite_token_hash = None
        lead.invite_expires_at = None
        logger.error("invite_failed", extra={"lead_id": lead.id, "error": str(exc)})
        return False

    lead.status = "invited"
    lead.invited_at = now
    logger.info("invite_sent", extra={"lead_id": lead.id, "role": lead.role})
    return True


def _send_latest_newsletter_issue(db: Session, lead: Lead) -> None:
    """Catch a brand-new, opted-in registrant up on the most recent issue.

    Best-effort: a failure here must never fail the registration itself, so
    it's logged rather than raised.
    """
    latest = db.query(NewsletterIssue).order_by(NewsletterIssue.sent_at.desc()).first()
    if latest is None:
        return

    unsubscribe_url = (
        f"{settings.public_api_url.rstrip('/')}/api/newsletter/unsubscribe?token={lead.unsubscribe_token}"
    )
    try:
        html, text = newsletter_email(latest.subject, latest.body_markdown, unsubscribe_url)
        get_email_sender().send(
            EmailMessage(
                to=lead.email,
                subject=latest.subject,
                html=html,
                text=text,
                list_unsubscribe=unsubscribe_url,
            )
        )
        logger.info("welcome_issue_sent", extra={"lead_id": lead.id, "issue_id": latest.id})
    except (EmailError, ValueError) as exc:
        logger.error("welcome_issue_failed", extra={"lead_id": lead.id, "error": str(exc)})


@router.post("/otp/send", response_model=OtpSendResult)
def send_lead_otp(payload: OtpSendRequest, db: Session = Depends(get_db)) -> OtpSendResult:
    """Email a 6-digit code so the registration form can confirm the address is real."""
    try:
        code, ttl = otp_module.issue(db, payload.email)
    except OtpError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    html, text = otp_email(code, max(1, ttl // 60))
    try:
        # ValueError covers a misconfigured sender (e.g. a missing API key) —
        # same failure mode as a delivery error from the caller's perspective.
        get_email_sender().send(
            EmailMessage(to=payload.email, subject="Your SocioTurtle verification code", html=html, text=text)
        )
    except (EmailError, ValueError) as exc:
        logger.error("otp_email_failed", extra={"email": payload.email, "error": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not send the code. Please try again."
        ) from exc

    return OtpSendResult(message="Verification code sent.", expires_in=ttl)


@router.post("/otp/verify", response_model=OtpVerifyResult)
def verify_lead_otp(payload: OtpVerifyRequest, db: Session = Depends(get_db)) -> OtpVerifyResult:
    """Confirm the code and return a short-lived token that unlocks POST /api/leads."""
    try:
        token = otp_module.verify(db, payload.email, payload.code)
    except OtpError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return OtpVerifyResult(verify_token=token)


@router.post("", response_model=LeadAccepted, status_code=status.HTTP_201_CREATED)
def register_lead(payload: LeadCreate, db: Session = Depends(get_db)) -> LeadAccepted:
    """Public endpoint used by the socioturtle.com site and widget.

    Requires an `email_verify_token` from a completed otp/send + otp/verify
    round trip for this exact email — that's the bot/abuse gate now, so no
    separate captcha is needed on top of it.
    """
    email = payload.email.lower()

    try:
        otp_module.redeem(db, email, payload.email_verify_token)
    except OtpError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    lead = db.query(Lead).filter(Lead.email == email).first()

    if lead is not None:
        # Re-registering is common (people forget). Refresh their details and
        # succeed quietly rather than leaking that the address is already on file.
        # Only overwrite a field when this submission actually provided one — the
        # email-only flow sends blank name/"unspecified" role, and that must not
        # clobber real data from an earlier, fuller registration.
        if payload.name.strip():
            lead.name = payload.name.strip()
        if payload.role != "unspecified":
            lead.role = payload.role
        if payload.phone.strip():
            lead.phone = payload.phone.strip()
        if payload.organisation.strip():
            lead.organisation = payload.organisation.strip()
        if payload.newsletter_opt_in:
            lead.newsletter_opt_in = True
        db.commit()
        logger.info("lead_updated", extra={"lead_id": lead.id, "role": lead.role})
    else:
        lead = Lead(
            name=payload.name.strip(),
            email=email,
            role=payload.role,
            phone=payload.phone.strip(),
            organisation=payload.organisation.strip(),
            source=payload.source.strip() or "website",
            newsletter_opt_in=payload.newsletter_opt_in,
            unsubscribe_token=secrets.token_urlsafe(32),
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        logger.info(
            "lead_registered",
            extra={
                "lead_id": lead.id,
                "role": lead.role,
                "source": lead.source,
                "newsletter": lead.newsletter_opt_in,
            },
        )
        if lead.newsletter_opt_in:
            _send_latest_newsletter_issue(db, lead)
        # Every registrant becomes a portal user (both student and mentor
        # access, not a role choice) — only employer leads are excluded.
        if lead.role != "employer":
            _mint_and_send_invite(db, lead)
            db.commit()

    return LeadAccepted(message="Thanks for registering. We will be in touch shortly.")


@router.get("", response_model=LeadList)
def list_leads(
    role: str | None = Query(None),
    lead_status: str | None = Query(None, alias="status"),
    q: str | None = Query(None, max_length=200),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> LeadList:
    stmt = select(Lead)
    if role:
        stmt = stmt.where(Lead.role == role)
    if lead_status:
        stmt = stmt.where(Lead.status == lead_status)
    if q:
        pattern = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            Lead.name.ilike(pattern) | Lead.email.ilike(pattern) | Lead.organisation.ilike(pattern)
        )

    total = len(db.execute(stmt.with_only_columns(Lead.id).order_by(None)).all())
    rows = db.execute(stmt.order_by(Lead.created_at.desc()).limit(limit).offset(offset))
    items = [LeadOut.model_validate(r) for r in rows.scalars().all()]

    counts = {
        "total": db.scalar(select(func.count()).select_from(Lead)) or 0,
        "student": db.scalar(
            select(func.count()).select_from(Lead).where(Lead.role == "student")
        )
        or 0,
        "mentor": db.scalar(select(func.count()).select_from(Lead).where(Lead.role == "mentor"))
        or 0,
        "employer": db.scalar(
            select(func.count()).select_from(Lead).where(Lead.role == "employer")
        )
        or 0,
        "unspecified": db.scalar(
            select(func.count()).select_from(Lead).where(Lead.role == "unspecified")
        )
        or 0,
        "new": db.scalar(select(func.count()).select_from(Lead).where(Lead.status == "new")) or 0,
        "invited": db.scalar(
            select(func.count()).select_from(Lead).where(Lead.status == "invited")
        )
        or 0,
        "activated": db.scalar(
            select(func.count()).select_from(Lead).where(Lead.status == "activated")
        )
        or 0,
        "newsletter": db.scalar(
            select(func.count()).select_from(Lead).where(Lead.newsletter_opt_in.is_(True))
        )
        or 0,
    }

    return LeadList(total=total, limit=limit, offset=offset, counts=counts, items=items)


@router.get("/export.csv")
def export_leads(
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id",
            "name",
            "email",
            "role",
            "phone",
            "organisation",
            "source",
            "newsletter_opt_in",
            "status",
            "created_at",
            "invited_at",
            "activated_at",
        ]
    )
    for lead in db.execute(select(Lead).order_by(Lead.created_at.desc())).scalars():
        writer.writerow(
            [
                lead.id,
                lead.name,
                lead.email,
                lead.role,
                lead.phone,
                lead.organisation,
                lead.source,
                lead.newsletter_opt_in,
                lead.status,
                lead.created_at,
                lead.invited_at or "",
                lead.activated_at or "",
            ]
        )

    logger.info("leads_exported")
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="socioturtle-leads.csv"'},
    )


@router.post("/invite", response_model=InviteResult)
def send_invites(
    payload: InviteRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> InviteResult:
    """Mint a one-time activation link per lead and email it.

    No password is generated or transmitted — the lead sets their own on arrival.
    """
    if payload.all_new:
        targets = db.execute(select(Lead).where(Lead.status == "new")).scalars().all()
    elif payload.lead_ids:
        targets = (
            db.execute(select(Lead).where(Lead.id.in_(payload.lead_ids))).scalars().all()
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide lead_ids or set all_new=true",
        )

    try:
        sender = get_email_sender()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Email sender is misconfigured: {exc}"
        ) from exc

    sent = skipped = failed = 0
    errors: list[str] = []

    with sender.connection() as conn:
        for lead in targets:
            if lead.status == "activated":
                skipped += 1
                continue
            if lead.status == "invited" and not payload.resend:
                skipped += 1
                continue
            if lead.role == "employer":
                # Employer leads are a contact list, not portal users.
                skipped += 1
                continue

            if _mint_and_send_invite(db, lead, sender=conn):
                sent += 1
            else:
                failed += 1
                errors.append(f"{lead.email}: delivery failed")

    db.commit()
    return InviteResult(sent=sent, skipped=skipped, failed=failed, errors=errors[:20])
