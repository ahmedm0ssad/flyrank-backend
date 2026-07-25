from datetime import datetime

from pydantic import BaseModel, Field


class ScrapedBookCreate(BaseModel):
    url: str = Field(..., max_length=500)
    title: str = Field(..., min_length=1, max_length=500)
    price: float | None = None
    availability: str | None = None
    rating: int | None = None
    description: str | None = None
    category: str | None = None
    upc: str | None = None
    image_url: str | None = None


class ScrapedBookUpdate(BaseModel):
    price: float | None = None
    availability: str | None = None
    rating: int | None = None
    description: str | None = None


class ScrapedBookResponse(BaseModel):
    id: int
    url: str
    title: str
    price: float | None = None
    availability: str | None = None
    rating: int | None = None
    description: str | None = None
    category: str | None = None
    upc: str | None = None
    image_url: str | None = None
    created_at: datetime
    updated_at: datetime
