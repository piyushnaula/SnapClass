"""Putting jobs on the Redis queue.

Jobs are referenced by their import path as a string (for example
"snapclass.workers.match_job.run_match"), so the API never imports the ML
code. Only the worker process imports and runs it.
"""

from redis.exceptions import RedisError
from rq import Callback, Queue, Retry
from rq.exceptions import NoSuchJobError
from rq.job import Job

from snapclass.core.errors import AppError
from snapclass.core.redis_client import get_redis
from snapclass.workers import callbacks

MATCH_QUEUE = "match"  # class photos: a teacher is waiting, so this queue goes first
ENROLL_QUEUE = "enroll"
QUEUE_NAMES = [MATCH_QUEUE, ENROLL_QUEUE]


def match_job_id(session_id: str) -> str:
    # A fixed id per session means the same session cannot be queued twice.
    return f"match-{session_id}"


def _queue(name: str) -> Queue:
    return Queue(name, connection=get_redis())


def enqueue_match(session_id: str) -> str:
    job_id = match_job_id(session_id)
    try:
        # Remove an old finished/failed job with the same id (teacher pressed "retry").
        try:
            Job.fetch(job_id, connection=get_redis()).delete()
        except NoSuchJobError:
            pass
        _queue(MATCH_QUEUE).enqueue(
            "snapclass.workers.match_job.run_match",
            session_id,
            job_id=job_id,
            job_timeout=600,
            retry=Retry(max=3, interval=[10, 30, 60]),
            on_failure=Callback(callbacks.match_failed),
        )
    except RedisError as exc:
        raise AppError(503, "QUEUE_UNAVAILABLE", "Job queue is unavailable, please try again shortly") from exc
    return job_id


def enqueue_enrollment(kind: str, job_id: str, student_id: str, keys: list[str]) -> None:
    function = (
        "snapclass.workers.enroll_job.enroll_face" if kind == "FACE" else "snapclass.workers.enroll_job.enroll_voice"
    )
    try:
        _queue(ENROLL_QUEUE).enqueue(
            function,
            job_id,
            student_id,
            keys,
            job_id=f"enroll-{job_id}",
            job_timeout=300,
            on_failure=Callback(callbacks.enrollment_failed),
        )
    except RedisError as exc:
        raise AppError(503, "QUEUE_UNAVAILABLE", "Job queue is unavailable, please try again shortly") from exc


def is_job_active(job_id: str) -> bool:
    """True if the job is waiting, scheduled for retry, or running."""
    try:
        status = Job.fetch(job_id, connection=get_redis()).get_status()
    except NoSuchJobError:
        return False
    return status in ("queued", "started", "scheduled", "deferred")


def queue_depths() -> dict[str, int]:
    return {name: _queue(name).count for name in QUEUE_NAMES}
