"""
Reusable FastAPI dependencies, e.g. resolving the current authenticated user
from the JWT bearer token.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.crud.user import get_user_by_id
from app.db.database import get_db
from app.db.models import User

# tokenUrl is only used for the interactive Swagger UI "Authorize" button.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    user_id_raw = payload.get("sub")
    if user_id_raw is None:
        raise credentials_exception

    try:
        user_id = int(user_id_raw)
    except (TypeError, ValueError):
        raise credentials_exception from None

    user = get_user_by_id(db, user_id)
    if user is None:
        raise credentials_exception

    return user


# Same as OAuth2PasswordBearer but does not raise if no token is provided,
# so public endpoints can optionally personalize their response for
# logged-in users (e.g. flagging watchlist membership) without requiring auth.
_optional_oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login", auto_error=False
)


def get_current_user_optional(
    token: str | None = Depends(_optional_oauth2_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    if not token:
        return None
    payload = decode_access_token(token)
    if payload is None:
        return None
    user_id_raw = payload.get("sub")
    if user_id_raw is None:
        return None
    try:
        user_id = int(user_id_raw)
    except (TypeError, ValueError):
        return None
    return get_user_by_id(db, user_id)

