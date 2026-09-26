import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from pydantic import BaseModel
from app.api.errors import (
    app_error_handler,
    global_exception_handler,
    request_validation_exception_handler,
)
from app.core.exceptions import AppError, NotFoundError
from app.core.config import settings

# We create a simple test application to directly test the handlers
# separated from the main app, to be able to raise test errors.
app_test = FastAPI()
app_test.add_exception_handler(AppError, app_error_handler)
app_test.add_exception_handler(Exception, global_exception_handler)
app_test.add_exception_handler(
    RequestValidationError, request_validation_exception_handler
)


class ValidationPayload(BaseModel):
    count: int

@app_test.get("/test-not-found")
def route_not_found():
    raise NotFoundError("Item not found test message")

@app_test.get("/test-internal-error")
def route_internal_error():
    raise ValueError("/internal/path credential-fragment")


@app_test.post("/test-validation")
def route_validation(payload: ValidationPayload):
    return payload

client = TestClient(app_test, raise_server_exceptions=False)

def test_app_error_handler_returns_correct_shape():
    response = client.get("/test-not-found")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "not_found"
    assert data["error"]["message"] == "Item not found test message"

def test_global_exception_handler_returns_safe_500():
    response = client.get("/test-internal-error")
    assert response.status_code == 500
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "internal_server_error"
    assert data["error"]["message"] == "An unexpected error occurred."
    
    # Ensure internals are not leaked in the content
    assert "ValueError" not in response.text
    assert "/internal/path" not in response.text
    assert "credential-fragment" not in response.text


def test_production_errors_and_validation_do_not_leak_details(monkeypatch, caplog):
    monkeypatch.setattr(settings, "app_env", "production")

    error_response = client.get("/test-internal-error")
    assert error_response.status_code == 500
    assert "credential-fragment" not in error_response.text
    assert "/internal/path" not in error_response.text

    validation_response = client.post(
        "/test-validation", json={"count": "credential-fragment"}
    )
    assert validation_response.status_code == 422
    assert validation_response.json() == {"detail": "Invalid request."}
    assert "credential-fragment" not in validation_response.text
    assert "/internal/path" not in caplog.text
    assert "credential-fragment" not in caplog.text

from fastapi import WebSocket

@app_test.websocket("/test-ws")
async def websocket_test(websocket: WebSocket):
    await websocket.accept()
    raise ValueError("WebSocket error test message")

def test_global_exception_handler_ignores_websocket():
    # WebSocket exceptions should NOT return JSONResponse, they should raise (and let ASGI server handle disconnect)
    with pytest.raises(ValueError, match="WebSocket error test message"):
        with client.websocket_connect("/test-ws"):
            pass

