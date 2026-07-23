from fastapi import APIRouter

from app.services import scraped_book_service

router = APIRouter(prefix="/scrape", tags=["scrape"])


@router.post("/")
async def trigger_scrape(max_pages: int = 5):
    return await scraped_book_service.start_scrape(max_pages)
