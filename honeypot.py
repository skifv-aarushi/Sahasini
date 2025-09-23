from fastapi import APIRouter, Request, HTTPException, Depends
from datetime import datetime
from sqlalchemy.orm import Session
from database import SessionLocal
from models import HoneypotLog
import logging

router = APIRouter()

# Configure logging
logging.basicConfig(filename="honeypot.log", level=logging.INFO)

# DB dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/user-location")
async def honeypot_endpoint(request: Request, db: Session = Depends(get_db)):
    ip = request.client.host
    user_agent = request.headers.get("user-agent", "unknown")
    timestamp = datetime.utcnow()

    # Log to file
    logging.info(f"Honeypot triggered at {timestamp.isoformat()} | IP: {ip} | UA: {user_agent}")

    # Log to DB
    log = HoneypotLog(ip=ip, user_agent=user_agent, timestamp=timestamp)
    db.add(log)
    db.commit()

    return {
        "message": "Access Denied",
        "status": "forbidden"
    }

#blocking honeypot IPs globally
def block_honeypot_ips(request: Request, db: Session = Depends(get_db)):
    ip = request.client.host
    flagged = db.query(HoneypotLog).filter(HoneypotLog.ip == ip).first()
    if flagged:
        raise HTTPException(status_code=403, detail="Access forbidden")
