import time
import requests
import json

SIMULATOR_URL = "http://localhost:9000"
BACKEND_URL = "http://localhost:8000"

def generate_traffic(seconds: int):
    end_time = time.time() + seconds
    while time.time() < end_time:
        try:
            requests.get(f"{SIMULATOR_URL}/api/checkout", timeout=1.0)
            requests.post(f"{SIMULATOR_URL}/webhook/payment-event", json={}, timeout=1.0)
        except Exception:
            pass
        time.sleep(0.5)

print("\n--- Step 3: Healthy Traffic ---")
requests.post(f"{SIMULATOR_URL}/simulate/reset")
generate_traffic(70)
r = requests.post(f"{BACKEND_URL}/detection/run")
print("POST /detection/run (healthy):", r.status_code, r.json())

print("\n--- Step 4: Trigger Bad Deployment ---")
requests.post(f"{SIMULATOR_URL}/simulate/bad-deployment")
generate_traffic(75)

print("\n--- Step 5: Detection Run (Bad Deployment) ---")
r = requests.post(f"{BACKEND_URL}/detection/run")
print("POST /detection/run (bad):", r.status_code, json.dumps(r.json(), indent=2))
incident_ids = [inc.get("id") for inc in r.json().get("new_incidents", [])]
print(f"Created Incident IDs: {incident_ids}")

print("\n--- Step 6: Deduplication Check ---")
r = requests.post(f"{BACKEND_URL}/detection/run")
print("POST /detection/run (dedup):", r.status_code, r.json())

print("\n--- Step 7: GET /incidents?status=open ---")
r = requests.get(f"{BACKEND_URL}/incidents?status=open")
print("GET /incidents?status=open:", r.status_code)
open_ids = [i.get("id") for i in r.json()]
print("Open Incident IDs:", open_ids)

print("\n--- Step 8: GET /incidents/{id} ---")
if incident_ids:
    r = requests.get(f"{BACKEND_URL}/incidents/{incident_ids[0]}")
    print(f"GET /incidents/{incident_ids[0]}:", r.status_code, r.json().get("id"))

print("\n--- Step 9: Invalid Status ---")
r = requests.get(f"{BACKEND_URL}/incidents?status=banana")
print("GET /incidents?status=banana:", r.status_code, r.text)
