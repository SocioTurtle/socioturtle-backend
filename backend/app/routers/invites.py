import hashlib
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.security import create_token, hash_password
from app.database import get_db
from app.models import Lead, User
from app.schemas import ActivateRequest, InviteCheck, TokenPair, UserOut

logger = logging.getLogger("app.invites")
router = APIRouter(prefix="/api/invites", tags=["invites"])


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _lookup(db: Session, raw_token: str) -> tuple[Lead | None, str | None]:
    lead = db.query(Lead).filter(Lead.invite_token_hash == _hash_token(raw_token)).first()
    if lead is None:
        return None, "This invitation link is not valid."
    if lead.status == "activated":
        return None, "This invitation has already been used."

    expires_at = lead.invite_expires_at
    if expires_at is None:
        return None, "This invitation link is not valid."
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        return None, "This invitation has expired. Ask us for a new one."
    return lead, None


@router.get("/{token}", response_model=InviteCheck)
def check_invite(token: str, db: Session = Depends(get_db)) -> InviteCheck:
    """Lets the activation screen greet the invitee before they submit anything."""
    lead, reason = _lookup(db, token)
    if lead is None:
        return InviteCheck(valid=False, reason=reason)
    return InviteCheck(valid=True, name=lead.name, email=lead.email, role=lead.role)


@router.post("/activate", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
def activate(payload: ActivateRequest, db: Session = Depends(get_db)) -> TokenPair:
    """Exchange a one-time invite token for a real account.

    The lead chooses their own password here; none was ever sent by email.
    """
    lead, reason = _lookup(db, payload.token)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reason)

    clash = (
        db.query(User)
        .filter(
            or_(
                User.email == lead.email,
                func.lower(User.username) == payload.username.lower(),
            )
        )
        .first()
    )
    if clash is not None:
        detail = (
            "An account already exists for this email."
            if clash.email == lead.email
            else "That username is taken. Please choose another."
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

    user = User(
        email=lead.email,
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=lead.role,
    )
    db.add(user)
    db.flush()

    lead.status = "activated"
    lead.activated_at = datetime.now(timezone.utc)
    lead.user_id = user.id
    # Burn the token so the link cannot be replayed.
    lead.invite_token_hash = None
    lead.invite_expires_at = None
    db.commit()
    db.refresh(user)

    logger.info("lead_activated", extra={"lead_id": lead.id, "user_id": user.id})

    access_token, expires_in = create_token(user.id, "access")
    refresh_token, _ = create_token(user.id, "refresh")
    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        user=UserOut.model_validate(user),
    )
