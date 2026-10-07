"""Functions RQ calls when a job fails.

RQ calls on_failure after EVERY failed attempt, even when it will retry. We
only mark the session FAILED after the last attempt (no retries left).
"""

import logging
import uuid

from sqlmodel import Session

from snapclass.core.db import engine
from snapclass.models import AttendanceSession, BiometricJob, utcnow

logger = logging.getLogger(__name__)


def match_failed(job, connection, exc_type, exc_value, traceback) -> None:  # noqa: ANN001
    if job.retries_left:
        logger.warning(
            "Match attempt failed, will retry", extra={"fields": {"job_id": job.id, "error": str(exc_value)}}
        )
        return
    session_id = uuid.UUID(job.args[0])
    with Session(engine) as db:
        session = db.get(AttendanceSession, session_id)
        if session is not None and session.status == "PROCESSING":
            session.status = "FAILED"
            session.error = f"Processing failed: {exc_value}"[:500]
            db.add(session)
            db.commit()
    logger.error("Match job failed", extra={"fields": {"job_id": job.id, "error": str(exc_value)}})


def enrollment_failed(job, connection, exc_type, exc_value, traceback) -> None:  # noqa: ANN001
    biometric_job_id = uuid.UUID(job.args[0])
    with Session(engine) as db:
        record = db.get(BiometricJob, biometric_job_id)
        if record is not None and record.status == "QUEUED":
            record.status = "FAILED"
            record.message = "Something went wrong while processing your upload. Please try again."
            record.finished_at = utcnow()
            db.add(record)
            db.commit()
    logger.error("Enrollment job failed", extra={"fields": {"job_id": job.id, "error": str(exc_value)}})
