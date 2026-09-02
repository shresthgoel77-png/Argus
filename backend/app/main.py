from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db import engine, Base
from app.api import health, detection, investigation, ai, remediation, verification, github, webhooks
from dotenv import load_dotenv

load_dotenv()

# Create tables if they don't exist
# We import models so they are registered with Base
import app.models 

Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Reliability Engineer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:3000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(detection.router)
app.include_router(investigation.router)
app.include_router(ai.router)
app.include_router(remediation.router)
app.include_router(verification.router)
app.include_router(github.router)
app.include_router(webhooks.router)

import os
import asyncio
import logging
from app.db import SessionLocal
from app.detection.engine import run_detection_pass

logger = logging.getLogger(__name__)

async def detection_poll_loop():
    poll_interval = int(os.getenv("DETECTION_POLL_INTERVAL_SECONDS", "10"))
    while True:
        await asyncio.sleep(poll_interval)
        try:
            db = SessionLocal()
            run_detection_pass(db, service="simulator")
            db.close()
        except Exception as e:
            logger.error(f"Error in background detection loop: {e}")

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(detection_poll_loop())

