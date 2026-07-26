import logging
import os
import sys

import redis
from dotenv import load_dotenv
from rq import Worker
from rq.worker import SimpleWorker

from app.queue import QUEUE_NAME, REDIS_URL, REPORT_QUEUE_NAME

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def run_worker():
    load_dotenv()
    redis_url = os.getenv("REDIS_URL", REDIS_URL)
    logger.info("Connecting to Redis at %s", redis_url)
    groq_key = os.getenv("GROQ_API_KEY")
    logger.info("GROQ_API_KEY present: %s", "yes" if groq_key else "no")

    try:
        connection = redis.from_url(redis_url, protocol=2)
        connection.ping()
        logger.info("Redis connection established")
    except redis.RedisError as e:
        logger.fatal("Cannot connect to Redis: %s", e)
        sys.exit(1)
        return

    queues = [QUEUE_NAME, REPORT_QUEUE_NAME]
    logger.info("Starting RQ worker for queues: %s", queues)

    worker_class = SimpleWorker if os.name == "nt" else Worker
    worker = worker_class(queues, connection=connection)
    worker.work()


if __name__ == "__main__":
    run_worker()
