from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, get_owned_profile
from app.models.user import User
from app.models.card import Card
from app.models.profile import SubjectProfile
from app.schemas.card import (
    CardCreate,
    CardResponse,
    CardReview,
    CardReviewResponse,
    CardListResponse,
    DueCardsResponse,
)

router = APIRouter()


@router.post("/", response_model=CardResponse, status_code=201)
async def create_card(
    card_data: CardCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_owned_profile(card_data.profile_id, user, db)

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
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Card)
    count_query = select(func.count(Card.id))

    if profile_id:
        await get_owned_profile(profile_id, user, db)
        query = query.where(Card.profile_id == profile_id)
        count_query = count_query.where(Card.profile_id == profile_id)
    elif not user.is_admin:
        owned = select(SubjectProfile.id).where(SubjectProfile.user_id == user.id)
        query = query.where(Card.profile_id.in_(owned))
        count_query = count_query.where(Card.profile_id.in_(owned))

    result = await db.execute(query.offset(skip).limit(limit))
    cards = result.scalars().all()

    count_result = await db.execute(count_query)
    total = count_result.scalar()

    return CardListResponse(
        cards=[CardResponse.model_validate(c) for c in cards],
        total=total,
    )


@router.get("/due", response_model=DueCardsResponse)
async def get_due_cards(
    profile_id: int | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all cards due for review today."""
    today = date.today()
    query = select(Card).where(Card.next_review <= today)

    if profile_id:
        await get_owned_profile(profile_id, user, db)
        query = query.where(Card.profile_id == profile_id)
    elif not user.is_admin:
        query = query.where(
            Card.profile_id.in_(
                select(SubjectProfile.id).where(SubjectProfile.user_id == user.id)
            )
        )

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
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Card).where(Card.id == card_id))
    card = result.scalar_one_or_none()

    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    await get_owned_profile(card.profile_id, user, db)

    return CardResponse.model_validate(card)


@router.post("/{card_id}/review", response_model=CardReviewResponse)
async def review_card(
    card_id: int,
    review: CardReview,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a review for a card, updating its SM-2 state.

    If the card is failed (quality 0-2), it stays in today's queue
    for immediate re-review.
    """
    result = await db.execute(select(Card).where(Card.id == card_id))
    card = result.scalar_one_or_none()

    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    await get_owned_profile(card.profile_id, user, db)

    failed = card.update_sm2(review.quality)
    await db.commit()
    await db.refresh(card)

    today = date.today()
    requeued = card.next_review <= today

    return CardReviewResponse(
        card=CardResponse.model_validate(card),
        failed=failed,
        requeued=requeued,
    )


@router.delete("/{card_id}", status_code=204)
async def delete_card(
    card_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Card).where(Card.id == card_id))
    card = result.scalar_one_or_none()

    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    await get_owned_profile(card.profile_id, user, db)

    await db.delete(card)
    await db.commit()
