"""Runtime settings stored in the app_settings table (editable by the admin)."""

import uuid

from sqlmodel import Session

from snapclass.domain.decisions import Thresholds
from snapclass.models import AppSetting, utcnow
from snapclass.services.audit import add_audit

DEFAULTS: dict[str, dict] = {
    "thresholds": Thresholds().to_dict(),
    "retention": {"days": 7},  # FR-A16: delete raw session media N days after finalize
    "enrollment": {"blur_threshold": 40.0, "min_face_px": 80},
}


def get_setting(db: Session, key: str) -> dict:
    row = db.get(AppSetting, key)
    return dict(row.value) if row else dict(DEFAULTS[key])


def get_thresholds(db: Session) -> Thresholds:
    return Thresholds.from_dict(get_setting(db, "thresholds"))


def all_settings(db: Session) -> dict:
    return {key: get_setting(db, key) for key in DEFAULTS}


def update_setting(db: Session, actor_id: uuid.UUID, key: str, changes: dict) -> dict:
    """Merge `changes` into a setting, audit it, and commit."""
    before = get_setting(db, key)
    after = {**before, **changes}
    row = db.get(AppSetting, key)
    if row is None:
        row = AppSetting(key=key, value=after)
    else:
        row.value = after
        row.updated_at = utcnow()
    db.add(row)
    add_audit(db, actor_id, "SETTINGS_CHANGE", "app_settings", key, before=before, after=after)
    db.commit()
    return after
