"""Start an RQ worker that processes match and enrollment jobs.

Run with:  python -m snapclass.workers.run_worker

We use SimpleWorker, which runs jobs in this same process instead of forking
a new process per job. Benefits: the models are loaded only once, and
PyTorch does not get into trouble with fork. If a job crashes the process,
Docker restarts the worker.
"""

import logging

from redis import Redis
from rq import SimpleWorker

from snapclass.core.config import settings
from snapclass.core.logging import setup_logging
from snapclass.workers.models_cache import get_face_encoder, get_voice_embedder
from snapclass.workers.queue import QUEUE_NAMES

logger = logging.getLogger(__name__)


def main() -> None:
    setup_logging()
    logger.info("Loading models")
    get_face_encoder()
    get_voice_embedder()
    logger.info("Models loaded, waiting for jobs", extra={"fields": {"queues": QUEUE_NAMES}})

    # The worker waits (blocks) on Redis for new jobs, so its connection must
    # NOT have the short read timeout that the API's connection uses.
    connection = Redis.from_url(settings.redis_url)
    worker = SimpleWorker(QUEUE_NAMES, connection=connection)
    # with_scheduler=True is needed for retries that wait (Retry interval).
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
