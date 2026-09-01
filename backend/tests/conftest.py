import pytest
import time
import httpx
import os

# Force alternative model for testing to avoid 429 quotas on gemini-2.5-flash
os.environ["AI_MODEL"] = "gemini-1.5-flash"

@pytest.fixture
def SIMULATOR_URL():
    return os.getenv("SIMULATOR_URL", "http://localhost:9000")

@pytest.fixture
def BACKEND_URL():
    return os.getenv("BACKEND_URL", "http://localhost:8000")

@pytest.fixture
def generate_traffic(SIMULATOR_URL):
    def _generate(seconds: float):
        end_time = time.time() + seconds
        while time.time() < end_time:
            try:
                # Use httpx for consistency with other newer tests, ignoring exceptions to keep generating
                httpx.get(f"{SIMULATOR_URL}/api/checkout", timeout=1.0)
                httpx.post(f"{SIMULATOR_URL}/webhook/payment-event", json={}, timeout=1.0)
            except Exception:
                pass
            time.sleep(0.5)
    return _generate
