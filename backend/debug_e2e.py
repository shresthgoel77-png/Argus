import time
import requests
import os
from app.detection import detectors
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)
SIMULATOR_URL = os.getenv("SIMULATOR_URL", "http://localhost:9000")

def generate_traffic(seconds: int):
    end_time = time.time() + seconds
    while time.time() < end_time:
        try:
            requests.get(f"{SIMULATOR_URL}/api/checkout", timeout=1.0)
            requests.post(f"{SIMULATOR_URL}/webhook/payment-event", json={}, timeout=1.0)
        except:
            pass
        time.sleep(0.5)

if __name__ == "__main__":
    print("Resetting...")
    requests.post(f"{SIMULATOR_URL}/simulate/reset")
    print("Generating 70s healthy...")
    generate_traffic(70)
    
    print("Setting bad...")
    requests.post(f"{SIMULATOR_URL}/simulate/bad-deployment")
    print("Generating 70s bad...")
    generate_traffic(70)
    
    print("Running detectors directly:")
    res_err = detectors.detect_high_error_rate("simulator")
    print("Err rate:", res_err)
    res_lat = detectors.detect_high_latency("simulator")
    print("Lat:", res_lat)
    
    print("Running engine via API:")
    res = client.post("/detection/run")
    print("Engine res:", res.json())
    
    requests.post(f"{SIMULATOR_URL}/simulate/reset")
