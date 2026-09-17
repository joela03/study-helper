from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.card import Card
from app.models.profile import SubjectProfile
from app.schemas.card import (
    CardCreate,
    CardResponse,
    CardReview,
    CardListResponse,
    DueCardsResponse,
)

router = APIRouter()


@router.post("/", response_model=CardResponse, status_code=201)
async def create_card(
    card_data: CardCreate,
    db: AsyncSession = Depends(get_db),
):
    # Verify profile exists
    result = await db.execute(
        select(SubjectProfile).where(SubjectProfile.id == card_data.profile_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Profile not found")

    card = Card(**card_data.model_dump())
    db.add(card)
    await db.commit()
    await db.refresh(card)
    return CardResponse.model_validate(card)


@router.get("/", response_model=CardListResponse)
async def list_cards(
    profile_id: int | None = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    query = select(Card)
    if profile_id:
        query = query.where(Card.profile_id == profile_id)

    result = await db.execute(query.offset(skip).limit(limit))
    cards = result.scalars().all()

    count_query = select(func.count(Card.id))
    if profile_id:
        count_query = count_query.where(Card.profile_id == profile_id)
    count_result = await db.execute(count_query)
    total = count_result.scalar()

    return CardListResponse(
        cards=[CardResponse.model_validate(c) for c in cards],
        total=total,
    )


@router.get("/due", response_model=DueCardsResponse)
async def get_due_cards(
    profile_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get all cards due for review today."""
    today = date.today()
    query = select(Card).where(Card.next_review <= today)

    if profile_id:
        query = query.where(Card.profile_id == profile_id)

    result = await db.execute(query)
    cards = result.scalars().all()

    return DueCardsResponse(
        cards=[CardResponse.model_validate(c) for c in cards],
        total_due=len(cards),
        profile_id=profile_id,
    )


@router.get("/{card_id}", response_model=CardResponse)
async def get_card(
    card_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Card).where(Card.id == card_id))
    card = result.scalar_one_or_none()

    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    return CardResponse.model_validate(card)


@router.post("/{card_id}/review", response_model=CardResponse)
async def review_card(
    card_id: int,
    review: CardReview,
    db: AsyncSession = Depends(get_db),
):
    """Submit a review for a card, updating its SM-2 state."""
    result = await db.execute(select(Card).where(Card.id == card_id))
    card = result.scalar_one_or_none()

    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    card.update_sm2(review.quality)
    await db.commit()
    await db.refresh(card)

    return CardResponse.model_validate(card)


@router.delete("/{card_id}", status_code=204)
async def delete_card(
    card_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Card).where(Card.id == card_id))
    card = result.scalar_one_or_none()

    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    await db.delete(card)
    await db.commit()
