from fastapi import FastAPI

app = FastAPI(title="RepoMedic Backend")

@app.get("/")
def read_root():
    return {"service": "repomedic-backend", "status": "ok"}
