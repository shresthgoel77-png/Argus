from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from fastapi import FastAPI, Request

from app.auth.clerk.adapter import ClerkAuthAdapter


@pytest.fixture(scope="module")
def signing_keys():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_key, public_key.decode()


@pytest.fixture
def request_factory():
    app = FastAPI()

    def make_request(authorization: str | None = None) -> Request:
        headers = []
        if authorization is not None:
            headers.append((b"authorization", authorization.encode()))
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": headers,
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
            "scheme": "http",
            "http_version": "1.1",
            "app": app,
        }
        return Request(scope)

    return make_request


def make_token(private_key, **claims):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "user_clerk_123",
        "email": "verified@example.com",
        "sid": "sess_123",
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(minutes=5),
        **claims,
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


@pytest.mark.asyncio
async def test_valid_token_returns_verified_identity(signing_keys, request_factory):
    private_key, public_key = signing_keys
    adapter = ClerkAuthAdapter(jwt_key=public_key)

    context = await adapter.resolve_identity(
        request_factory(f"Bearer {make_token(private_key)}")
    )

    assert context is not None
    assert context.external_id == "user_clerk_123"
    assert context.email == "verified@example.com"
    assert context.provider == "clerk"


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["expired", "malformed"])
async def test_expired_and_malformed_tokens_are_rejected(
    signing_keys, request_factory, kind
):
    private_key, public_key = signing_keys
    token = (
        make_token(private_key, exp=datetime.now(timezone.utc) - timedelta(minutes=1))
        if kind == "expired"
        else "not-a-jwt"
    )
    adapter = ClerkAuthAdapter(jwt_key=public_key)

    assert await adapter.resolve_identity(request_factory(f"Bearer {token}")) is None


@pytest.mark.asyncio
async def test_tampered_signature_is_rejected(signing_keys, request_factory):
    private_key, public_key = signing_keys
    token = make_token(private_key)
    header, payload, signature = token.split(".")
    replacement = "a" if signature[0] != "a" else "b"
    tampered_token = ".".join((header, payload, replacement + signature[1:]))
    adapter = ClerkAuthAdapter(jwt_key=public_key)

    assert (
        await adapter.resolve_identity(request_factory(f"Bearer {tampered_token}"))
        is None
    )


@pytest.mark.asyncio
async def test_mismatched_authorized_party_is_rejected(signing_keys, request_factory):
    private_key, public_key = signing_keys
    adapter = ClerkAuthAdapter(
        jwt_key=public_key,
        authorized_parties=["https://app.example.com"],
    )
    token = make_token(private_key, azp="https://attacker.example")

    assert await adapter.resolve_identity(request_factory(f"Bearer {token}")) is None
@pytest.mark.asyncio
@pytest.mark.parametrize('stage', ['verification', 'email_lookup'])
async def test_slow_clerk_call_does_not_block_other_requests(request_factory, stage):
    import asyncio
    import threading
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    released = threading.Event()
    state = SimpleNamespace(is_signed_in=True, payload={'sub': 'user_verified'})
    if stage == 'verification':
        state.payload['email'] = 'verified@example.com'
    user = SimpleNamespace(email_addresses=[SimpleNamespace(email_address='verified@example.com')])
    client = MagicMock()
    def blocked(result):
        def call(*args, **kwargs):
            if not released.wait(timeout=1):
                raise TimeoutError('The event loop could not service another request')
            return result
        return call
    client.authenticate_request.return_value = state
    client.users.get.return_value = user
    if stage == 'verification':
        client.authenticate_request.side_effect = blocked(state)
    else:
        client.users.get.side_effect = blocked(user)
    adapter = ClerkAuthAdapter(clerk_client=client)
    async def other_request():
        released.set()
    context, _ = await asyncio.gather(adapter.resolve_identity(request_factory()), other_request())
    assert context is not None and context.external_id == 'user_verified'
