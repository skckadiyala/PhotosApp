import uuid
from pydantic import BaseModel, Field


class PersonUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class PersonMerge(BaseModel):
    source_id: uuid.UUID
    target_id: uuid.UUID
