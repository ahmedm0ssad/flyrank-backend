import os
import uuid
from datetime import datetime, timezone

import redis
from rq import Queue, Retry

from app.models.job import JobResponse, JobStatus

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
IDEMPOTENCY_TTL = 86400
JOB_TTL = 86400
QUEUE_NAME = "ai-jobs"
REPORT_QUEUE_NAME = "report-jobs"

_connection: redis.Redis | None = None
_queue: Queue | None = None
_report_queue: Queue | None = None


def get_connection() -> redis.Redis:
    global _connection
    if _connection is None:
        _connection = redis.from_url(REDIS_URL, decode_responses=True, protocol=2)
    return _connection


def get_queue() -> Queue:
    global _queue
    if _queue is None:
        _queue = Queue(QUEUE_NAME, connection=get_connection())
    return _queue


def get_report_queue() -> Queue:
    global _report_queue
    if _report_queue is None:
        _report_queue = Queue(REPORT_QUEUE_NAME, connection=get_connection())
    return _report_queue


def reset_connection():
    global _connection, _queue, _report_queue
    if _connection:
        _connection.close()
    _connection = None
    _queue = None
    _report_queue = None


def create_job(
    payload: dict, idempotency_key: str | None = None
) -> tuple[str, JobStatus]:
    conn = get_connection()

    if idempotency_key:
        existing_job_id = conn.get(f"idempotency:{idempotency_key}")
        if existing_job_id:
            return existing_job_id, JobStatus.QUEUED

    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    conn.hset(
        f"job:{job_id}",
        mapping={
            "status": JobStatus.QUEUED.value,
            "created_at": now,
            "updated_at": now,
            "attempts": "0",
        },
    )
    conn.expire(f"job:{job_id}", JOB_TTL)

    retry = Retry(max=3, interval=[10, 60, 300])
    queue = get_queue()
    queue.enqueue(
        "app.services.ai_worker.run_ai_job",
        payload,
        job_id=job_id,
        retry=retry,
        job_timeout=600,
        meta={"max_retries": 3},
    )

    if idempotency_key:
        conn.setex(f"idempotency:{idempotency_key}", IDEMPOTENCY_TTL, job_id)

    return job_id, JobStatus.QUEUED


def get_job(job_id: str) -> JobResponse | None:
    conn = get_connection()
    data = conn.hgetall(f"job:{job_id}")
    if not data:
        return None

    return JobResponse(
        job_id=job_id,
        status=JobStatus(data.get("status", JobStatus.QUEUED.value)),
        result=data.get("result"),
        error=data.get("error"),
        created_at=data.get("created_at"),
        started_at=data.get("started_at"),
        finished_at=data.get("finished_at"),
        attempts=int(data.get("attempts", 0)),
    )


def update_job(job_id: str, status: str, **extra):
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()
    mapping = {"status": status, "updated_at": now}
    mapping.update(extra)
    conn.hset(f"job:{job_id}", mapping=mapping)
    conn.expire(f"job:{job_id}", JOB_TTL)


def list_jobs(limit: int = 20, offset: int = 0) -> list[JobResponse]:
    conn = get_connection()
    cursor = 0
    job_keys: list[bytes] = []
    while True:
        cursor, keys = conn.scan(cursor=cursor, match="job:*", count=100)
        job_keys.extend(keys)
        if cursor == 0:
            break

    job_keys = sorted(job_keys, reverse=True)
    jobs = []
    for key in job_keys[offset : offset + limit]:
        if isinstance(key, bytes):
            key = key.decode()
        job_id = key.split(":", 1)[1]
        job = get_job(job_id)
        if job:
            jobs.append(job)
    return jobs


def create_report_job() -> tuple[str, JobStatus]:
    conn = get_connection()

    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    conn.hset(
        f"report_job:{job_id}",
        mapping={
            "status": JobStatus.QUEUED.value,
            "created_at": now,
            "updated_at": now,
            "attempts": "0",
        },
    )
    conn.expire(f"report_job:{job_id}", JOB_TTL)

    retry = Retry(max=3, interval=[10, 60, 300])
    report_queue = get_report_queue()
    report_queue.enqueue(
        "app.services.report_worker.run_report_job",
        job_id,
        job_id=job_id,
        retry=retry,
        job_timeout=600,
        meta={"max_retries": 3},
    )

    return job_id, JobStatus.QUEUED


def get_report_job(job_id: str) -> JobResponse | None:
    conn = get_connection()
    data = conn.hgetall(f"report_job:{job_id}")
    if not data:
        return None

    return JobResponse(
        job_id=job_id,
        status=JobStatus(data.get("status", JobStatus.QUEUED.value)),
        result=data.get("result"),
        error=data.get("error"),
        created_at=data.get("created_at"),
        started_at=data.get("started_at"),
        finished_at=data.get("finished_at"),
        attempts=int(data.get("attempts", 0)),
    )


def update_report_job(job_id: str, status: str, **extra):
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()
    mapping = {"status": status, "updated_at": now}
    mapping.update(extra)
    conn.hset(f"report_job:{job_id}", mapping=mapping)
    conn.expire(f"report_job:{job_id}", JOB_TTL)
