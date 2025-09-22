from pydantic import BaseModel
from typing import Optional

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
