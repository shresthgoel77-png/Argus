from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
try:
    res = client.post("/detection/run")
    print("Status:", res.status_code)
    print("Response:", res.json())
except Exception as e:
    import traceback
    traceback.print_exc()
