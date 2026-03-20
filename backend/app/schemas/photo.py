import uuid
from datetime import datetime
from pydantic import BaseModel


class PhotoBase(BaseModel):
    """Summary photo object returned in list views."""
    id: uuid.UUID
    file_name: str
    mime_type: str
    file_size: int | None = None
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
    host_file_path: str | None = None  # absolute path on the host machine
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


class MonthPhotosResponse(BaseModel):
    """Photos for a specific month."""
    year: int
    month: int
    count: int
    items: list[PhotoBase]


class CoverPhotoInfo(BaseModel):
    """Minimal photo info used as a cover image."""
    id: uuid.UUID


class MonthSummary(BaseModel):
    """Aggregated data for one calendar month."""
    year: int
    month: int
    key: str          # e.g. "2024-12"
    label: str        # e.g. "December 2024"
    count: int
    cover_photos: list[CoverPhotoInfo]  # up to 4 for mosaic


class YearSummary(BaseModel):
    """Aggregated data for one calendar year."""
    year: int
    count: int
    cover_photo: CoverPhotoInfo | None
    months: list[MonthSummary]


class LibrarySummaryResponse(BaseModel):
    """Full library summary — replaces fetching all pages for year/month views."""
    years: list[YearSummary]
    total: int
