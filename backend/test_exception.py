from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app.api.errors import global_exception_handler
import sys

app = FastAPI()
app.add_exception_handler(Exception, global_exception_handler)

@app.get("/test/{item_id}")
def read_item(item_id: int):
    if item_id == 0:
        raise HTTPException(status_code=404, detail="Not Found")
    return {"item_id": item_id}

client = TestClient(app)
try:
    print("422 Error:", client.get("/test/abc").json())
    print("404 Error:", client.get("/test/0").json())
except Exception as e:
    print(e)
