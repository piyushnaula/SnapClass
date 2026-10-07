import uuid

from fastapi import APIRouter, Query

from snapclass.api.deps import Admin, DbSession
from snapclass.core.errors import bad_request
from snapclass.domain.decisions import Thresholds
from snapclass.schemas import SettingsUpdate, TeacherCreate, UserOut, UserStatusUpdate
from snapclass.services import admin_service, settings_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/metrics")
def metrics(admin: Admin, db: DbSession) -> dict:
    return admin_service.metrics(db)


@router.get("/teachers", response_model=list[UserOut])
def list_teachers(admin: Admin, db: DbSession) -> list:
    return admin_service.list_teachers(db)


@router.post("/teachers", response_model=UserOut, status_code=201)
def create_teacher(body: TeacherCreate, admin: Admin, db: DbSession) -> object:
    return admin_service.create_teacher(db, admin, body)


@router.patch("/users/{user_id}", response_model=UserOut)
def set_user_status(user_id: uuid.UUID, body: UserStatusUpdate, admin: Admin, db: DbSession) -> object:
    return admin_service.set_user_active(db, admin, user_id, body.is_active)


@router.get("/settings")
def get_settings(admin: Admin, db: DbSession) -> dict:
    return settings_service.all_settings(db)


@router.put("/settings")
def update_settings(body: SettingsUpdate, admin: Admin, db: DbSession) -> dict:
    if body.thresholds is not None:
        unknown = set(body.thresholds) - set(Thresholds.__dataclass_fields__)
        if unknown:
            raise bad_request(f"Unknown threshold names: {', '.join(sorted(unknown))}")
        merged = Thresholds.from_dict({**settings_service.get_setting(db, "thresholds"), **body.thresholds})
        if merged.problems():
            raise bad_request("Invalid thresholds: " + "; ".join(merged.problems()))
        settings_service.update_setting(db, admin.id, "thresholds", body.thresholds)
    if body.retention_days is not None:
        settings_service.update_setting(db, admin.id, "retention", {"days": body.retention_days})
    if body.blur_threshold is not None:
        settings_service.update_setting(db, admin.id, "enrollment", {"blur_threshold": body.blur_threshold})
    return settings_service.all_settings(db)


@router.get("/audit")
def audit_log(admin: Admin, db: DbSession, limit: int = Query(default=50, ge=1, le=500)) -> list:
    return admin_service.audit_entries(db, limit)
