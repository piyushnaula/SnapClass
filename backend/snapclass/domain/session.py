"""Session state machine (spec A.8.2, extended so photos can be changed before saving).

All status changes go through `check_transition`, so the rules live in one place.

    CREATED ──add photos──▶ UPLOADED ──check──▶ PROCESSING ──ok──▶ REVIEW ──save──▶ FINALIZED
       ▲                     │   ▲                  │                 │
       └──all photos removed─┘   │                  │ fail            │ add / remove photos
                                 │                  ▼                 │ (check again)
                                 └──── photos ── FAILED ◀─────────────┘
                                       changed     │ retry → PROCESSING

Photos can be changed in every state except PROCESSING (the worker is reading them)
and FINALIZED (attendance is saved; use corrections instead).
"""

from enum import StrEnum


class SessionStatus(StrEnum):
    CREATED = "CREATED"
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    REVIEW = "REVIEW"
    FINALIZED = "FINALIZED"
    FAILED = "FAILED"


ALLOWED_TRANSITIONS: dict[SessionStatus, set[SessionStatus]] = {
    SessionStatus.CREATED: {SessionStatus.UPLOADED},
    SessionStatus.UPLOADED: {SessionStatus.PROCESSING, SessionStatus.CREATED},
    SessionStatus.PROCESSING: {SessionStatus.REVIEW, SessionStatus.FAILED},
    SessionStatus.FAILED: {SessionStatus.PROCESSING, SessionStatus.UPLOADED, SessionStatus.CREATED},
    SessionStatus.REVIEW: {SessionStatus.FINALIZED, SessionStatus.UPLOADED, SessionStatus.CREATED},
    SessionStatus.FINALIZED: set(),  # corrections keep it FINALIZED (audited separately)
}


class InvalidTransition(Exception):
    """Raised for a status change the state machine does not allow (HTTP 409)."""


def check_transition(current: str, target: str) -> None:
    current_status = SessionStatus(current)
    target_status = SessionStatus(target)
    if target_status not in ALLOWED_TRANSITIONS[current_status]:
        raise InvalidTransition(f"Cannot move session from {current} to {target}")


def can_change_media(status: str) -> bool:
    """Photos/audio may be added or removed in every state except while checking or after saving."""
    return status not in (SessionStatus.PROCESSING, SessionStatus.FINALIZED)


def status_after_media_change(has_media: bool) -> SessionStatus:
    """After photos are added or removed, the session waits for a (new) check."""
    return SessionStatus.UPLOADED if has_media else SessionStatus.CREATED
