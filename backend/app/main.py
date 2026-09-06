from fastapi import FastAPI
from app.api.v1.health import router as health_router

app = FastAPI(title="RepoMedic Backend")

@app.get("/")
def read_root():
    return {"service": "repomedic-backend", "status": "ok"}

app.include_router(health_router, prefix="/api/v1")
