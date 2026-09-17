from datetime import datetime, date
from typing import Optional

from pydantic import BaseModel, Field

from app.models.card import CardType


class CardCreate(BaseModel):
    profile_id: int
    transcript_id: Optional[int] = None
    card_type: CardType = CardType.FLASHCARD
    question: str
    answer: str


class CardResponse(BaseModel):
    id: int
    profile_id: int
    transcript_id: Optional[int]
    card_type: CardType
    question: str
    answer: str
    ease_factor: float
    interval: int
    repetitions: int
    next_review: date
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CardReview(BaseModel):
    """Submit a review for a card."""
    quality: int = Field(..., ge=0, le=5, description="0-2 = fail, 3-5 = pass")


class CardListResponse(BaseModel):
    cards: list[CardResponse]
    total: int


class DueCardsResponse(BaseModel):
    """Cards due for review today."""
    cards: list[CardResponse]
    total_due: int
    profile_id: Optional[int] = None
