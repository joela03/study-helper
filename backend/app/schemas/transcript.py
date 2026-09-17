from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.transcript import TranscriptStatus


class TranscriptCreate(BaseModel):
    title: str
    profile_id: int


class TranscriptResponse(BaseModel):
    id: int
    profile_id: int
    title: str
    status: TranscriptStatus
    document_path: Optional[str]
    audio_path: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    chunk_count: int = 0

    class Config:
        from_attributes = True


class TranscriptListResponse(BaseModel):
    transcripts: list[TranscriptResponse]
    total: int
