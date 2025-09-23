from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
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
    semantic_cluster = Column(Integer, nullable=True)
    geo_cluster = Column(Integer, nullable=True)
    risk_score = Column(Float, nullable=True)
    risk_level = Column(String, nullable=True)

    # Relationships
    forks = relationship(
        "Incident",
        remote_side=[id],
        foreign_keys=[parent_id],
        backref="parent",
    )

class HoneypotLog(Base):
    __tablename__ = "honeypot_logs"

    id = Column(Integer, primary_key=True, index=True)
    ip = Column(String, nullable=False)
    user_agent = Column(String, nullable=True)
