"""Audit log helper (FR-A15).

The caller commits. That way the audit entry and the change it describes are
saved in the same transaction: either both are stored or neither is.
"""

import uuid

from sqlmodel import Session

from snapclass.models import AuditLog


def add_audit(
    db: Session,
    actor_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: str | uuid.UUID,
    before: dict | None = None,
    after: dict | None = None,
    reason: str | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            before=before,
            after=after,
            reason=reason,
        )
    )
