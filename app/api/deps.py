"""
Reusable FastAPI dependencies, e.g. resolving the current authenticated user
from the JWT bearer token.
"""

import secrets

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import decode_access_token
from app.crud.user import get_user_by_id
from app.db.database import get_db
from app.db.models import User

logger = get_logger(__name__)


def require_internal_api_token(
    internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
) -> None:
    """Authenticate scheduled jobs using a separately configured secret."""
    configured_token = settings.INTERNAL_API_TOKEN
    if configured_token is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal API token is not configured",
        )
    if internal_token is None or not secrets.compare_digest(
        internal_token, configured_token
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal API token",
            headers={"WWW-Authenticate": "Internal"},
        )


# tokenUrl is only used for the interactive Swagger UI "Authorize" button.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def _resolve_user_from_token(
    request: Request,
    token: str | None,
    db: Session,
) -> User | None:
    if not token:
        return None
    payload = decode_access_token(token)
    if payload is None:
        logger.warning("jwt decode failed or token invalid/expired")
        return None

    user_id_raw = payload.get("sub")
    if user_id_raw is None:
        logger.warning("jwt missing sub claim")
        return None

    try:
        user_id = int(user_id_raw)
    except (TypeError, ValueError):
        logger.warning("jwt sub claim is not a valid user id", extra={"sub": user_id_raw})
        return None

    user = get_user_by_id(db, user_id)
    if user is None:
        logger.warning("jwt valid but user no longer exists", extra={"user_id": user_id})
        return None

    request.state.user_id = user.id
    return user


def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    user = _resolve_user_from_token(request, token, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


# Same as OAuth2PasswordBearer but does not raise if no token is provided,
# so public endpoints can optionally personalize their response for
# logged-in users (e.g. flagging watchlist membership) without requiring auth.
_optional_oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login", auto_error=False
)


def get_current_user_optional(
    request: Request,
    token: str | None = Depends(_optional_oauth2_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    return _resolve_user_from_token(request, token, db)
