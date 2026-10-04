from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_user, get_owned_profile
from app.models.user import User
from app.models.profile import SubjectProfile
from app.models.card import Card
from app.schemas.profile import (
    ProfileCreate,
    ProfileUpdate,
    ProfileResponse,
    ProfileListResponse,
)

router = APIRouter()


@router.post("/", response_model=ProfileResponse, status_code=201)
async def create_profile(
    profile_data: ProfileCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = SubjectProfile(**profile_data.model_dump(), user_id=user.id)
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return ProfileResponse(
        **profile.__dict__,
        transcript_count=0,
        card_count=0,
        due_card_count=0,
    )


@router.get("/", response_model=ProfileListResponse)
async def list_profiles(
    skip: int = 0,
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(SubjectProfile).options(
        selectinload(SubjectProfile.transcripts), selectinload(SubjectProfile.cards)
    )
    count_query = select(func.count(SubjectProfile.id))

    # Admins see every subject; everyone else sees their own
    if not user.is_admin:
        query = query.where(SubjectProfile.user_id == user.id)
        count_query = count_query.where(SubjectProfile.user_id == user.id)

    result = await db.execute(query.offset(skip).limit(limit))
    profiles = result.scalars().all()

    count_result = await db.execute(count_query)
    total = count_result.scalar()

    today = date.today()
    profile_responses = []
    for p in profiles:
        due_count = sum(1 for c in p.cards if c.next_review <= today)
        profile_responses.append(
            ProfileResponse(
                **{k: v for k, v in p.__dict__.items() if not k.startswith("_")},
                transcript_count=len(p.transcripts),
                card_count=len(p.cards),
                due_card_count=due_count,
            )
        )

    return ProfileListResponse(profiles=profile_responses, total=total)


@router.get("/{profile_id}", response_model=ProfileResponse)
async def get_profile(
    profile_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SubjectProfile)
        .options(selectinload(SubjectProfile.transcripts), selectinload(SubjectProfile.cards))
        .where(SubjectProfile.id == profile_id)
    )
    profile = result.scalar_one_or_none()

    if not profile or (profile.user_id != user.id and not user.is_admin):
        raise HTTPException(status_code=404, detail="Profile not found")

    today = date.today()
    due_count = sum(1 for c in profile.cards if c.next_review <= today)

    return ProfileResponse(
        **{k: v for k, v in profile.__dict__.items() if not k.startswith("_")},
        transcript_count=len(profile.transcripts),
        card_count=len(profile.cards),
        due_card_count=due_count,
    )


@router.patch("/{profile_id}", response_model=ProfileResponse)
async def update_profile(
    profile_id: int,
    profile_data: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SubjectProfile)
        .options(selectinload(SubjectProfile.transcripts), selectinload(SubjectProfile.cards))
        .where(SubjectProfile.id == profile_id)
    )
    profile = result.scalar_one_or_none()

    if not profile or (profile.user_id != user.id and not user.is_admin):
        raise HTTPException(status_code=404, detail="Profile not found")

    update_data = profile_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    await db.commit()
    await db.refresh(profile)

    today = date.today()
    due_count = sum(1 for c in profile.cards if c.next_review <= today)

    return ProfileResponse(
        **{k: v for k, v in profile.__dict__.items() if not k.startswith("_")},
        transcript_count=len(profile.transcripts),
        card_count=len(profile.cards),
        due_card_count=due_count,
    )


@router.delete("/{profile_id}", status_code=204)
async def delete_profile(
    profile_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SubjectProfile).where(SubjectProfile.id == profile_id)
    )
    profile = result.scalar_one_or_none()

    if not profile or (profile.user_id != user.id and not user.is_admin):
        raise HTTPException(status_code=404, detail="Profile not found")

    await db.delete(profile)
    await db.commit()
