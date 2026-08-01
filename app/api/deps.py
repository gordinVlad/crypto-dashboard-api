"""
Reusable FastAPI dependencies, e.g. resolving the current authenticated user
from the JWT bearer token.
"""

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.security import decode_access_token
from app.crud.user import get_user_by_id
from app.db.database import get_db
from app.db.models import User

logger = get_logger(__name__)

# tokenUrl is only used for the interactive Swagger UI "Authorize" button.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        logger.warning("jwt decode failed or token invalid/expired")
        raise credentials_exception

    user_id_raw = payload.get("sub")
    if user_id_raw is None:
        logger.warning("jwt missing sub claim")
        raise credentials_exception

    try:
        user_id = int(user_id_raw)
    except (TypeError, ValueError):
        logger.warning("jwt sub claim is not a valid user id", extra={"sub": user_id_raw})
        raise credentials_exception from None

    user = get_user_by_id(db, user_id)
    if user is None:
        logger.warning("jwt valid but user no longer exists", extra={"user_id": user_id})
        raise credentials_exception

    request.state.user_id = user.id
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

