from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import SessionLocal, engine, Base
from models import Incident
from schemas import IncidentCreate, IncidentResponse, MergeRequest

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Sahasini Backend")

# DB Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---- CREATE INCIDENT ----
@app.post("/incidents/", response_model=IncidentResponse)
def create_incident(incident: IncidentCreate, db: Session = Depends(get_db)):
    db_incident = Incident(**incident.dict())
    db.add(db_incident)
    db.commit()
    db.refresh(db_incident)

    # generate unique parent_id (use id itself)
    db_incident.parent_id = db_incident.id
    db.add(db_incident)
    db.commit()
    db.refresh(db_incident)

    return db_incident

# ---- LIST INCIDENTS ----
@app.get("/incidents/", response_model=List[IncidentResponse])
def list_incidents(db: Session = Depends(get_db)):
    return db.query(Incident).all()

# ---- FORK INCIDENT ----
@app.post("/incidents/{incident_id}/fork", response_model=IncidentResponse)
def fork_incident(incident_id: int, fork: IncidentCreate, db: Session = Depends(get_db)):
    parent = db.query(Incident).filter(Incident.id == incident_id).first()
    if not parent:
        raise HTTPException(status_code=404, detail="Parent incident not found")

    db_incident = Incident(**fork.dict(), parent_id=incident_id)
    db.add(db_incident)
    db.commit()
    db.refresh(db_incident)
    return db_incident

# ---- MERGE INCIDENTS ----
@app.post("/incidents/merge/")
def merge_incidents(request: MergeRequest, db: Session = Depends(get_db)):
    parent = db.query(Incident).filter(Incident.id == request.parent_id).first()
    if not parent:
        raise HTTPException(status_code=404, detail="Parent incident not found")

    for mid in request.merge_ids:
        incident = db.query(Incident).filter(Incident.id == mid).first()
        if incident and incident.id != request.parent_id:
            parent.description += f" | Merged: {incident.description}"
            incident.merged_into = request.parent_id
            db.add(incident)

    db.add(parent)
    db.commit()
    db.refresh(parent)

    return {
        "message": f"Merged {len(request.merge_ids)} incidents into {request.parent_id}",
        "parent_incident": parent.id,
        "new_description": parent.description
    }

# ---- GET CLUSTERS (PRECOMPUTED) ----
@app.get("/clusters/")
def get_clusters(db: Session = Depends(get_db)):
    # Fetch only active (not merged) incidents
    incidents = db.query(Incident).filter(Incident.merged_into.is_(None)).all()
    if not incidents:
        return {"clusters": []}

    clusters = {}
    for inc in incidents:
        # use semantic_cluster or geo_cluster (precomputed in ML pipeline)
        clusters[inc.id] = {
            "semantic_cluster": inc.semantic_cluster,
            "geo_cluster": inc.geo_cluster,
            "risk_score": inc.risk_score,
            "risk_level": inc.risk_level
        }

    return {"clusters": clusters}
