import logging

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.captcha import CaptchaError, get_captcha_provider
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import (
    CaptchaChallengeOut,
    LoginRequest,
    RefreshRequest,
    SignupRequest,
    TokenPair,
    UserOut,
)

logger = logging.getLogger("app.auth")
router = APIRouter(prefix="/api/auth", tags=["auth"])

_INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
)


def _issue_tokens(user: User) -> TokenPair:
    access_token, expires_in = create_token(user.id, "access")
    refresh_token, _ = create_token(user.id, "refresh")
    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        user=UserOut.model_validate(user),
    )


def _verify_captcha(db: Session, payload) -> None:
    try:
        get_captcha_provider().verify(db, payload.captcha)
    except CaptchaError as exc:
        logger.warning("captcha_failed", extra={"reason": str(exc)})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/captcha", response_model=CaptchaChallengeOut)
def get_captcha(db: Session = Depends(get_db)) -> CaptchaChallengeOut:
    try:
        return get_captcha_provider().issue(db)
    except CaptchaError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc)) from exc


@router.post("/signup", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> TokenPair:
    _verify_captcha(db, payload)

    email = payload.email.lower()
    exists = (
        db.query(User)
        .filter(or_(User.email == email, func.lower(User.username) == payload.username.lower()))
        .first()
    )
    if exists is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email or username already registered"
        )

    user = User(
        email=email,
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info("user_signed_up", extra={"user_id": user.id, "role": user.role})
    return _issue_tokens(user)


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenPair:
    _verify_captcha(db, payload)

    identifier = payload.identifier.lower()
    user = (
        db.query(User)
        .filter(or_(User.email == identifier, func.lower(User.username) == identifier))
        .first()
    )
    if user is None or not verify_password(payload.password, user.password_hash):
        logger.warning("login_failed", extra={"identifier": identifier})
        raise _INVALID_CREDENTIALS
    if not user.is_active:
        raise _INVALID_CREDENTIALS

    logger.info("login_succeeded", extra={"user_id": user.id, "role": user.role})
    return _issue_tokens(user)


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenPair:
    try:
        claims = decode_token(payload.refresh_token, "refresh")
    except jwt.PyJWTError as exc:
        raise _INVALID_CREDENTIALS from exc

    user = db.get(User, int(claims["sub"]))
    if user is None or not user.is_active:
        raise _INVALID_CREDENTIALS
    return _issue_tokens(user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)
