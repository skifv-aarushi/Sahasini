from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import SessionLocal, engine, Base
from models import Incident
from schemas import IncidentCreate, IncidentResponse, MergeRequest

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans

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
    # Step 1: insert incident without parent_id
    db_incident = Incident(**incident.dict())
    db.add(db_incident)
    db.commit()
    db.refresh(db_incident)

    # Step 2: generate unique parent_id (use id itself)
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
            # combine descriptions
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

# ---- CLUSTER INCIDENTS ----
@app.get("/clusters/")
def cluster_incidents(db: Session = Depends(get_db)):
    # cluster only active (not merged) incidents
    incidents = db.query(Incident).filter(Incident.merged_into.is_(None)).all()
    if not incidents:
        return {"clusters": []}

    descriptions = [i.description for i in incidents]
    tfidf = TfidfVectorizer()
    X = tfidf.fit_transform(descriptions)
    kmeans = KMeans(n_clusters=min(3, len(descriptions)), random_state=0).fit(X)
    clusters = {i.id: int(label) for i, label in zip(incidents, kmeans.labels_)}
    return {"clusters": clusters}
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import SessionLocal, engine, Base
from models import Incident
from schemas import IncidentCreate, IncidentResponse

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Sahasini Backend")

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Create new incident – parent_id generated automatically
@app.post("/incidents/", response_model=IncidentResponse)
def create_incident(incident: IncidentCreate, db: Session = Depends(get_db)):
    db_incident = Incident(**incident.dict())       # no parent_id from client
    db.add(db_incident)
    db.commit()
    db.refresh(db_incident)

    # assign its own id as parent_id
    db_incident.parent_id = db_incident.id
    db.add(db_incident)
    db.commit()
    db.refresh(db_incident)
    return db_incident

# List all incidents
@app.get("/incidents/", response_model=List[IncidentResponse])
def list_incidents(db: Session = Depends(get_db)):
    return db.query(Incident).all()

# Fork an incident
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

# Merge incidents (mark merged_into)
@app.post("/incidents/merge/")
def merge_incidents(parent_id: int, merge_ids: List[int], db: Session = Depends(get_db)):
    for mid in merge_ids:
        incident = db.query(Incident).filter(Incident.id == mid).first()
        if incident:
            incident.merged_into = parent_id
            db.add(incident)
    db.commit()
    return {"message": f"Merged {len(merge_ids)} incidents into {parent_id}"}

# AI clustering endpoint
@app.get("/clusters/")
def cluster_incidents(db: Session = Depends(get_db)):
    incidents = db.query(Incident).all()
    if not incidents:
        return {"clusters": []}

    descriptions = [i.description for i in incidents]
    tfidf = TfidfVectorizer()
    X = tfidf.fit_transform(descriptions)
    kmeans = KMeans(n_clusters=min(3, len(descriptions)), random_state=0).fit(X)
    clusters = {i.id: int(label) for i, label in zip(incidents, kmeans.labels_)}
    return {"clusters": clusters}
