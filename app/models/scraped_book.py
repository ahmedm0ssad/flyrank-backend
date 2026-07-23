from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ScrapedBookCreate(BaseModel):
    url: str = Field(..., max_length=500)
    title: str = Field(..., min_length=1, max_length=500)
    price: Optional[float] = None
    availability: Optional[str] = None
    rating: Optional[int] = None
    description: Optional[str] = None
    category: Optional[str] = None
    upc: Optional[str] = None
    image_url: Optional[str] = None


class ScrapedBookUpdate(BaseModel):
    price: Optional[float] = None
    availability: Optional[str] = None
    rating: Optional[int] = None
    description: Optional[str] = None


class ScrapedBookResponse(BaseModel):
    id: int
    url: str
    title: str
    price: Optional[float] = None
    availability: Optional[str] = None
    rating: Optional[int] = None
    description: Optional[str] = None
    category: Optional[str] = None
    upc: Optional[str] = None
    image_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime
