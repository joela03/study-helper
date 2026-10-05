"""Registration, login and the current account."""
from datetime import datetime, timedelta, timezone
import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.models.invite import InviteCode
from app.core.config import settings

router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(..., min_length=1, max_length=120)
    password: str = Field(..., min_length=8, max_length=200)
    invite_code: str | None = None


class InviteCreate(BaseModel):
    note: str | None = Field(None, max_length=255, description="Who it's for")
    max_uses: int = Field(1, ge=1, le=500)
    expires_in_days: int | None = Field(None, ge=1, le=365)


class InviteResponse(BaseModel):
    id: int
    code: str
    note: str | None
    max_uses: int
    uses: int
    expires_at: datetime | None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Avoids characters that get misread when a code is typed from a message
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_code(length: int = 10) -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    display_name: str
    is_admin: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    invite: InviteCode | None = None

    if settings.REQUIRE_INVITE:
        if not request.invite_code:
            raise HTTPException(
                status_code=403, detail="An invite code is required to sign up"
            )

        found = await db.execute(
            select(InviteCode).where(
                func.upper(InviteCode.code) == request.invite_code.strip().upper()
            )
        )
        invite = found.scalar_one_or_none()

        # One message for every failure mode, so the endpoint can't be used
        # to probe which codes exist or how much life is left in them
        if not invite or not invite.is_redeemable(now):
            raise HTTPException(
                status_code=403, detail="That invite code isn't valid"
            )

    existing = await db.execute(
        select(User).where(func.lower(User.email) == request.email.lower())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="That email is already registered")

    user = User(
        email=request.email.lower(),
        display_name=request.display_name,
        password_hash=hash_password(request.password),
    )
    db.add(user)

    if invite:
        invite.uses += 1

    await db.commit()
    await db.refresh(user)

    return TokenResponse(
        access_token=create_access_token(user.id),
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(func.lower(User.email) == request.email.lower())
    )
    user = result.scalar_one_or_none()

    # Same message either way: don't reveal which emails exist
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Wrong email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account is disabled")

    return TokenResponse(
        access_token=create_access_token(user.id),
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return UserResponse.model_validate(user)


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin only: who has an account."""
    result = await db.execute(select(User).order_by(User.created_at))
    return [UserResponse.model_validate(u) for u in result.scalars().all()]


@router.post("/invites", response_model=InviteResponse, status_code=201)
async def create_invite(
    request: InviteCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin only: mint a code someone can register with."""
    expires_at = None
    if request.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=request.expires_in_days)

    # Retry on the vanishingly unlikely collision rather than 500
    for _ in range(5):
        code = generate_code()
        clash = await db.execute(select(InviteCode).where(InviteCode.code == code))
        if not clash.scalar_one_or_none():
            break
    else:
        raise HTTPException(status_code=500, detail="Couldn't allocate a code")

    invite = InviteCode(
        code=code,
        created_by_id=admin.id,
        note=request.note,
        max_uses=request.max_uses,
        expires_at=expires_at,
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)

    return InviteResponse.model_validate(invite)


@router.get("/invites", response_model=list[InviteResponse])
async def list_invites(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(InviteCode).order_by(InviteCode.created_at.desc()))
    return [InviteResponse.model_validate(i) for i in result.scalars().all()]


@router.delete("/invites/{invite_id}", status_code=204)
async def revoke_invite(
    invite_id: int,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate rather than delete, so spent codes stay auditable."""
    result = await db.execute(select(InviteCode).where(InviteCode.id == invite_id))
    invite = result.scalar_one_or_none()

    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")

    invite.is_active = False
    await db.commit()
