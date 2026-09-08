import asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.main import app

@app.get("/trigger-error")
def trigger_error():
    raise ValueError("Real app error")

client = TestClient(app, raise_server_exceptions=False)
response = client.get("/trigger-error")
print("Status Code:", response.status_code)
print("Response:", response.json())
