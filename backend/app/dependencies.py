import logging

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.database import get_db
from app.models import User

logger = logging.getLogger("app.auth")
bearer_scheme = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise _UNAUTHORIZED
    try:
        payload = decode_token(credentials.credentials, "access")
    except jwt.PyJWTError as exc:
        logger.warning("token_rejected", extra={"reason": str(exc)})
        raise _UNAUTHORIZED from exc

    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise _UNAUTHORIZED
    return user


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        logger.warning("admin_access_denied", extra={"user_id": user.id})
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user
