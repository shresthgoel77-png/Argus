import pytest
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from app.auth.development.adapter import DevelopmentAuthProvider
from app.auth.development.constants import DEV_USER_EMAIL, DEV_USER_EXTERNAL_ID

@pytest.fixture
def auth_provider():
    return DevelopmentAuthProvider()

@pytest.fixture
def test_app(auth_provider):
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test_secret_key")
    
    @app.get("/me")
    async def get_me(request: Request):
        ctx = await auth_provider.resolve_identity(request)
        if not ctx:
            return {"authenticated": False}
        return {
            "authenticated": True,
            "email": ctx.email,
            "external_id": ctx.external_id,
            "provider": ctx.provider
        }

    @app.post("/login")
    async def do_login(request: Request, response: Response):
        await auth_provider.login(request, response)
        return {"ok": True}

    @app.post("/logout")
    async def do_logout(request: Request, response: Response):
        await auth_provider.logout(request, response)
        return {"ok": True}

    return app

@pytest.fixture
def client(test_app):
    return TestClient(test_app)

def test_unauthenticated(client):
    response = client.get("/me")
    assert response.status_code == 200
    assert response.json()["authenticated"] is False

def test_login_and_resolve(client):
    # Login sets the cookie
    login_resp = client.post("/login")
    assert login_resp.status_code == 200
    assert "session" in login_resp.cookies
    
    # Resolving identity with the cookie
    me_resp = client.get("/me")
    assert me_resp.status_code == 200
    data = me_resp.json()
    assert data["authenticated"] is True
    assert data["email"] == DEV_USER_EMAIL
    assert data["external_id"] == DEV_USER_EXTERNAL_ID
    assert data["provider"] == "development"

def test_logout(client):
    client.post("/login")
    me1 = client.get("/me")
    assert me1.json()["authenticated"] is True
    
    # Logout clears the cookie
    client.post("/logout")
    
    me2 = client.get("/me")
    assert me2.json()["authenticated"] is False

def test_invalid_tampered_cookie(client):
    client.post("/login")
    # Tamper with the cookie locally, mocking client storage
    client.cookies.set("session", "tampered_invalid_data")
    
    # Middleware will drop the invalid cookie silently and request.session will be empty
    me_resp = client.get("/me")
    assert me_resp.json()["authenticated"] is False
