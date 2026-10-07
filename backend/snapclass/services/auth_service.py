"""Login, refresh-token rotation and logout (FR-A1).

Refresh tokens rotate: every refresh returns a NEW refresh token and revokes
the old one. If someone uses an already revoked token, it was probably stolen,
so we revoke every active token of that user (reuse detection).
"""

import logging
from datetime import timedelta

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from snapclass.core.config import settings
from snapclass.core.errors import AppError, conflict
from snapclass.core.rate_limit import is_rate_limited
from snapclass.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    hash_password,
    hash_token,
    new_refresh_token,
    verify_password,
)
from snapclass.models import RefreshToken, User, utcnow

logger = logging.getLogger(__name__)

INVALID_LOGIN = AppError(401, "INVALID_CREDENTIALS", "Student ID / email or password is incorrect")


def find_user(db: Session, login_id: str) -> User | None:
    """An "@" means an email (teachers, admin); anything else is a student ID."""
    login_id = login_id.strip()
    if "@" in login_id:
        return db.exec(select(User).where(User.email == login_id.lower())).first()
    return db.exec(select(User).where(User.roll_no == login_id.upper(), User.role == "STUDENT")).first()


def authenticate(db: Session, login_id: str, password: str) -> User:
    """Return the user if the login ID + password are correct. Same error for every failure."""
    user = find_user(db, login_id)
    if user is None:
        verify_password(password, DUMMY_PASSWORD_HASH)  # same timing as a real check
        raise INVALID_LOGIN
    if not verify_password(password, user.password_hash) or not user.is_active:
        raise INVALID_LOGIN
    return user


def check_login_rate_limit(ip: str, login_id: str) -> None:
    ip_limited = is_rate_limited(f"rl:login:ip:{ip}", settings.login_limit_per_ip_per_minute, 60)
    account_limited = is_rate_limited(
        f"rl:login:acct:{login_id.strip().lower()}", settings.login_limit_per_account_per_hour, 3600
    )
    if ip_limited or account_limited:
        raise AppError(429, "RATE_LIMITED", "Too many login attempts. Please wait and try again.")


def issue_tokens(db: Session, user: User) -> tuple[str, str, RefreshToken]:
    """Create an access token and a new refresh token (saved only as a hash). Caller commits."""
    refresh = new_refresh_token()
    record = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh),
        expires_at=utcnow() + timedelta(days=settings.refresh_token_days),
    )
    db.add(record)
    return create_access_token(user.id, user.role), refresh, record


def login(db: Session, login_id: str, password: str, ip: str) -> tuple[User, str, str]:
    check_login_rate_limit(ip, login_id)
    user = authenticate(db, login_id, password)
    access, refresh, _ = issue_tokens(db, user)
    db.commit()
    logger.info("Login", extra={"fields": {"user_id": str(user.id)}})
    return user, access, refresh


def register_student(db: Session, student_id: str, full_name: str, password: str, ip: str) -> tuple[User, str, str]:
    """A student creates an account with their college student ID, then is signed in."""
    if is_rate_limited(f"rl:register:ip:{ip}", 5, 3600):
        raise AppError(429, "RATE_LIMITED", "Too many new accounts from this device. Please try again later.")
    taken = conflict(
        "An account with this student ID already exists. Sign in instead, or ask your teacher if it is not yours.",
        "STUDENT_ID_TAKEN",
    )
    if db.exec(select(User).where(User.roll_no == student_id)).first() is not None:
        raise taken
    student = User(roll_no=student_id, full_name=full_name, password_hash=hash_password(password), role="STUDENT")
    db.add(student)
    try:
        db.flush()  # the UNIQUE constraint also catches two sign-ups at the same moment
    except IntegrityError:
        db.rollback()
        raise taken from None
    access, refresh, _ = issue_tokens(db, student)
    db.commit()
    db.refresh(student)
    logger.info("Student registered", extra={"fields": {"user_id": str(student.id)}})
    return student, access, refresh


def rotate_refresh_token(db: Session, token: str) -> tuple[User, str, str]:
    invalid = AppError(401, "INVALID_REFRESH_TOKEN", "Please log in again")
    record = db.exec(select(RefreshToken).where(RefreshToken.token_hash == hash_token(token))).first()
    if record is None:
        raise invalid

    if record.revoked_at is not None:
        # Reuse of a revoked token → assume theft, log the user out everywhere.
        revoke_all_for_user(db, record.user_id)
        db.commit()
        logger.warning("Refresh token reuse detected", extra={"fields": {"user_id": str(record.user_id)}})
        raise invalid

    if record.expires_at < utcnow():
        raise invalid

    user = db.get(User, record.user_id)
    if user is None or not user.is_active:
        raise invalid

    access, new_refresh, new_record = issue_tokens(db, user)
    # Insert the new row first, because the old row will point to it (foreign key).
    db.flush()
    record.revoked_at = utcnow()
    record.replaced_by = new_record.id
    db.add(record)
    db.commit()
    return user, access, new_refresh


def revoke_all_for_user(db: Session, user_id) -> None:
    active = db.exec(
        select(RefreshToken).where(RefreshToken.user_id == user_id, col(RefreshToken.revoked_at).is_(None))
    ).all()
    for token in active:
        token.revoked_at = utcnow()
        db.add(token)


def logout(db: Session, token: str) -> None:
    record = db.exec(select(RefreshToken).where(RefreshToken.token_hash == hash_token(token))).first()
    if record is not None and record.revoked_at is None:
        record.revoked_at = utcnow()
        db.add(record)
        db.commit()
