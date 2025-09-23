from fastapi import FastAPI, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List

from database import SessionLocal, engine, Base
from models import Incident
from schemas import IncidentCreate, IncidentResponse, MergeRequest
from honeypot import router as honeypot_router, block_honeypot_ips

import asyncio
import socketio
from starlette.concurrency import run_in_threadpool  # type: ignore

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi import status


Base.metadata.create_all(bind=engine)

sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
sio_app = socketio.ASGIApp(sio)

app = FastAPI(title="Sahasini Backend")
app.mount("/ws", sio_app)

#database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update this with your frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add error handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": str(exc)},
    )

# Update the create_incident endpoint to include validation
@app.post("/incidents/", response_model=IncidentResponse, dependencies=[Depends(block_honeypot_ips)])
async def create_incident(incident: IncidentCreate, db: Session = Depends(get_db)):
    try:
        db_incident = await run_in_threadpool(_create_incident_sync, incident.dict(), db)
        await sio.emit("incident_created", {"incident": IncidentResponse.from_orm(db_incident).dict()})
        return db_incident
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create incident: {str(e)}"
        )

# Add status endpoint to check API health
@app.get("/status")
async def check_status():
    return {"status": "operational"}



def _create_incident_sync(incident_data: dict, db: Session):
    db_incident = Incident(**incident_data)
    db.add(db_incident)
    db.commit()
    db.refresh(db_incident)
    db_incident.parent_id = db_incident.id
    db.add(db_incident)
    db.commit()
    db.refresh(db_incident)
    return db_incident

def _fork_incident_sync(parent_id: int, fork_data: dict, db: Session):
    parent = db.query(Incident).filter(Incident.id == parent_id).first()
    if not parent:
        return None
    db_incident = Incident(**fork_data, parent_id=parent_id)
    db.add(db_incident)
    db.commit()
    db.refresh(db_incident)
    return db_incident

def _merge_incidents_sync(request: dict, db: Session):
    parent = db.query(Incident).filter(Incident.id == request["parent_id"]).first()
    if not parent:
        return None
    for mid in request["merge_ids"]:
        incident = db.query(Incident).filter(Incident.id == mid).first()
        if incident and incident.id != request["parent_id"]:
            parent.description = (parent.description or "") + f" | Merged: {incident.description or ''}"
            incident.merged_into = request["parent_id"]
            db.add(incident)
    db.add(parent)
    db.commit()
    db.refresh(parent)
    return parent


# REST Endpoints

@app.post("/incidents/", response_model=IncidentResponse, dependencies=[Depends(block_honeypot_ips)])
async def create_incident(incident: IncidentCreate, db: Session = Depends(get_db)):
    db_incident = await run_in_threadpool(_create_incident_sync, incident.dict(), db)
    asyncio.create_task(
        sio.emit("incident_created", {"incident": IncidentResponse.from_orm(db_incident).dict()})
    )
    return db_incident

@app.get("/incidents/", response_model=List[IncidentResponse])
async def list_incidents(db: Session = Depends(get_db)):
    incidents = await run_in_threadpool(lambda: db.query(Incident).all())
    return incidents

@app.post("/incidents/{incident_id}/fork", response_model=IncidentResponse, dependencies=[Depends(block_honeypot_ips)])
async def fork_incident(incident_id: int, fork: IncidentCreate, db: Session = Depends(get_db)):
    db_incident = await run_in_threadpool(_fork_incident_sync, incident_id, fork.dict(), db)
    if not db_incident:
        raise HTTPException(status_code=404, detail="Parent incident not found")
    asyncio.create_task(
        sio.emit("incident_forked", {"parent_id": incident_id, "incident": IncidentResponse.from_orm(db_incident).dict()})
    )
    return db_incident

@app.post("/incidents/merge/", dependencies=[Depends(block_honeypot_ips)])
async def merge_incidents(request: MergeRequest, db: Session = Depends(get_db)):
    parent = await run_in_threadpool(_merge_incidents_sync, request.dict(), db)
    if not parent:
        raise HTTPException(status_code=404, detail="Parent incident not found")
    asyncio.create_task(
        sio.emit("incidents_merged", {"parent_id": request.parent_id, "merge_ids": request.merge_ids, "new_description": parent.description})
    )
    return {
        "message": f"Merged {len(request.merge_ids)} incidents into {request.parent_id}",
        "parent_incident": parent.id,
        "new_description": parent.description
    }

@app.get("/clusters/", dependencies=[Depends(block_honeypot_ips)])
async def get_clusters(db: Session = Depends(get_db)):
    incidents = await run_in_threadpool(lambda: db.query(Incident).filter(Incident.merged_into.is_(None)).all())
    if not incidents:
        return {"clusters": []}
    clusters = {}
    for inc in incidents:
        clusters[inc.id] = {
            "semantic_cluster": inc.semantic_cluster,
            "geo_cluster": inc.geo_cluster,
            "risk_score": inc.risk_score,
            "risk_level": inc.risk_level
        }
    return {"clusters": clusters}


@sio.event
async def connect(sid, environ):
    client_ip = environ.get("REMOTE_ADDR") or environ.get("HTTP_X_FORWARDED_FOR")
    if client_ip and await run_in_threadpool(block_honeypot_ips, Request(scope=environ)):
        print(f"Blocked honeypot IP attempted WebSocket connection: {client_ip}")
        await sio.disconnect(sid)
    else:
        print(f"Socket.IO client connected: {client_ip}")

app.include_router(honeypot_router)
