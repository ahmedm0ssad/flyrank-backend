import logging
import os
import sys

import redis
from rq import Worker

from app.queue import QUEUE_NAME, REDIS_URL

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def run_worker():
    redis_url = os.getenv("REDIS_URL", REDIS_URL)
    logger.info("Connecting to Redis at %s", redis_url)

    try:
        connection = redis.from_url(redis_url, decode_responses=True, protocol=2)
        connection.ping()
        logger.info("Redis connection established")
    except redis.RedisError as e:
        logger.fatal("Cannot connect to Redis: %s", e)
        sys.exit(1)
        return

    queues = [QUEUE_NAME]
    logger.info("Starting RQ worker for queues: %s", queues)

    worker = Worker(queues, connection=connection)
    worker.work()


if __name__ == "__main__":
    run_worker()
