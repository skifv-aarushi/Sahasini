from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("incidents.id"), nullable=True)
    merged_into = Column(Integer, ForeignKey("incidents.id"), nullable=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    incident_type = Column(String, nullable=False)
    timestamp = Column(String, nullable=False)

    # Relationships
    forks = relationship(
        "Incident",
        remote_side=[id],
        foreign_keys=[parent_id],
        backref="parent",  # optional, makes .parent accessible
    )
