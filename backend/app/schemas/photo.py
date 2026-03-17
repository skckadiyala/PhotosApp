import uuid
from datetime import datetime
from pydantic import BaseModel


class PhotoBase(BaseModel):
    """Summary photo object returned in list views."""
    id: uuid.UUID
    file_name: str
    mime_type: str
    width: int | None = None
    height: int | None = None
    taken_at: datetime | None = None
    is_favorite: bool = False
    thumb_sm: str | None = None
    thumb_md: str | None = None

    model_config = {"from_attributes": True}


class PhotoDetail(PhotoBase):
    """Full photo object returned for single-photo views."""
    file_path: str
    file_size: int
    file_hash: str
    camera_make: str | None = None
    camera_model: str | None = None
    lens_model: str | None = None
    f_number: float | None = None
    exposure_time: str | None = None
    iso: int | None = None
    focal_length: float | None = None
    orientation: int | None = None
    gps_latitude: float | None = None
    gps_longitude: float | None = None
    location_name: str | None = None
    is_hidden: bool = False
    is_processed: bool = False
    thumb_lg: str | None = None
    created_at: datetime
    updated_at: datetime


class PhotoMetadataResponse(BaseModel):
    """EXIF metadata response for GET /photos/metadata/{id}."""
    id: uuid.UUID
    file_name: str
    file_path: str
    file_size: int
    file_hash: str
    mime_type: str
    width: int | None = None
    height: int | None = None
    taken_at: datetime | None = None
    camera_make: str | None = None
    camera_model: str | None = None
    lens_model: str | None = None
    f_number: float | None = None
    exposure_time: str | None = None
    iso: int | None = None
    focal_length: float | None = None
    orientation: int | None = None
    gps_latitude: float | None = None
    gps_longitude: float | None = None

    model_config = {"from_attributes": True}


class PaginatedPhotos(BaseModel):
    """Paginated list response."""
    items: list[PhotoBase]
    page: int
    limit: int
    total: int
    total_pages: int
