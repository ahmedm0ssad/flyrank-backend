from enum import Enum

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    QUEUED = "queued"
    STARTED = "started"
    FINISHED = "finished"
    FAILED = "failed"


class JobCreate(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=10000)
    model: str = "llama-3.1-8b-instant"


class JobEnqueueResponse(BaseModel):
    job_id: str
    status: JobStatus = JobStatus.QUEUED
    status_url: str = ""


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    result: str | None = None
    error: str | None = None
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    attempts: int = 0


class JobListResponse(BaseModel):
    jobs: list[JobResponse]
    total: int
