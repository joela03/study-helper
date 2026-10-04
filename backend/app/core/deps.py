"""
Request dependencies for authentication and ownership.

Ownership is checked at the subject: transcripts, cards, concepts and
materials all hang off a profile, so one check covers them.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.profile import SubjectProfile
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    unauthorised = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not credentials:
        raise unauthorised

    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise unauthorised

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise unauthorised

    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    return user


async def get_owned_profile(
    profile_id: int,
    user: User,
    db: AsyncSession,
) -> SubjectProfile:
    """
    Fetch a subject the user is allowed to touch.

    Returns 404 rather than 403 for someone else's subject, so the endpoint
    doesn't confirm that an id exists to a user who can't see it. Admins can
    reach anything.
    """
    result = await db.execute(
        select(SubjectProfile).where(SubjectProfile.id == profile_id)
    )
    profile = result.scalar_one_or_none()

    if not profile or (profile.user_id != user.id and not user.is_admin):
        raise HTTPException(status_code=404, detail="Profile not found")

    return profile
