import os

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from app.services.report_service import enqueue_report, get_report_metadata

router = APIRouter(prefix="/reports", tags=["reports"])

REPORTS_DIR = "generated_reports"
ALLOWED_EXTENSION = ".pdf"


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def create_report():
    result = await enqueue_report()
    return result


@router.get("/{job_id}")
async def get_report(job_id: str):
    metadata = await get_report_metadata(job_id)
    if metadata is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )
    return metadata


@router.get("/files/{filename}")
async def download_report(filename: str):
    if not filename.endswith(ALLOWED_EXTENSION):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type",
        )

    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename",
        )

    filepath = os.path.normpath(os.path.join(REPORTS_DIR, filename))
    if not filepath.startswith(os.path.normpath(REPORTS_DIR)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename",
        )

    if not os.path.exists(filepath):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report file not found",
        )

    return FileResponse(
        filepath,
        media_type="application/pdf",
        filename=filename,
    )
