"""Shared FastAPI dependencies: database session, current user, role checks (RBAC)."""

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from snapclass.core.db import get_db
from snapclass.core.errors import AppError
from snapclass.core.logging import user_id_var
from snapclass.core.security import decode_access_token
from snapclass.models import User

bearer = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    unauthorized = AppError(401, "UNAUTHORIZED", "Please log in")
    if credentials is None:
        raise unauthorized
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise unauthorized
    user = db.get(User, uuid.UUID(payload["sub"]))
    if user is None or not user.is_active:
        raise unauthorized
    user_id_var.set(str(user.id))  # shows up in every log line of this request
    return user


def require_role(*roles: str) -> Callable[..., User]:
    """Dependency factory: `Depends(require_role("TEACHER"))` allows only teachers."""

    def checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles:
            raise AppError(403, "FORBIDDEN", "You do not have access to this action")
        return user

    return checker


CurrentUser = Annotated[User, Depends(get_current_user)]
Teacher = Annotated[User, Depends(require_role("TEACHER"))]
Student = Annotated[User, Depends(require_role("STUDENT"))]
Admin = Annotated[User, Depends(require_role("ADMIN"))]
