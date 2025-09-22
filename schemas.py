from pydantic import BaseModel
from typing import Optional, List

class IncidentCreate(BaseModel):
    title: str
    description: str
    latitude: float
    longitude: float
    incident_type: str
    timestamp: str

class IncidentResponse(BaseModel):
    id: int
    parent_id: Optional[int]
    merged_into: Optional[int]
    title: str
    description: str
    latitude: float
    longitude: float
    incident_type: str
    timestamp: str

    class Config:
        orm_mode = True

# Merge request schema for merge endpoint
class MergeRequest(BaseModel):
    parent_id: int
    merge_ids: List[int]
