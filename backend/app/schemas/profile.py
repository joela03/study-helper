from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ProfileCreate(BaseModel):
    name: str
    module_code: Optional[str] = None
    module_spec: Optional[str] = None


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    module_code: Optional[str] = None
    module_spec: Optional[str] = None


class ProfileResponse(BaseModel):
    id: int
    name: str
    module_code: Optional[str]
    module_spec: Optional[str]
    created_at: datetime
    updated_at: datetime

    # Counts
    transcript_count: int = 0
    card_count: int = 0
    due_card_count: int = 0

    class Config:
        from_attributes = True


class ProfileListResponse(BaseModel):
    profiles: list[ProfileResponse]
    total: int
