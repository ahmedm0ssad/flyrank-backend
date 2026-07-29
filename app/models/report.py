from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class ReportStatus(str, Enum):
    QUEUED = "queued"
    STARTED = "started"
    FINISHED = "finished"
    FAILED = "failed"


class ReportResponse(BaseModel):
    report_id: int
    job_id: str
    status: ReportStatus
    file_path: str | None = None
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ReportMetadataResponse(BaseModel):
    job_id: str
    status: ReportStatus
    download_url: str | None = None
    error: str | None = None
