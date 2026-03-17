import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class AlbumCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class AlbumUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    cover_photo_id: uuid.UUID | None = None


class AlbumResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    cover_photo_id: uuid.UUID | None = None
    is_smart: bool = False
    photo_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AlbumPhotoAdd(BaseModel):
    photo_ids: list[uuid.UUID]
