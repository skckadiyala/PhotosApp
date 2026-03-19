import uuid
from datetime import datetime

from pydantic import BaseModel


class FaceBase(BaseModel):
    """A detected face in a photo."""
    id: uuid.UUID
    photo_id: uuid.UUID
    person_id: uuid.UUID | None = None
    bbox_top: int
    bbox_right: int
    bbox_bottom: int
    bbox_left: int
    confidence: float = 0.0
    match_distance: float = 0.0
    status: str = "confirmed"
    created_at: datetime

    model_config = {"from_attributes": True}


class PersonBase(BaseModel):
    """A named person (face cluster)."""
    id: uuid.UUID
    name: str | None = None
    face_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PersonDetail(PersonBase):
    """Person with their face records."""
    faces: list[FaceBase] = []


class PersonNameRequest(BaseModel):
    """Request body for naming a person."""
    name: str


class MergePeopleRequest(BaseModel):
    """Request body for merging two face clusters."""
    person_id_keep: uuid.UUID
    person_id_merge: uuid.UUID


class FaceAssignRequest(BaseModel):
    """Request body for assigning a face to a person."""
    person_id: uuid.UUID | None = None
    new_person_name: str | None = None


class ClusterRequest(BaseModel):
    """Optional tuning params for re-clustering."""
    eps: float = 0.5
    min_samples: int = 2
