import time
import requests
import json
import subprocess
import os

BACKEND_URL = "http://localhost:8000"
SIMULATOR_URL = "http://localhost:9000"

print("\n--- Step 10: Prometheus-unavailable behavior ---")
subprocess.run("powershell -Command \"$pid_kill = (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue).OwningProcess; if ($pid_kill) { Stop-Process -Id $pid_kill -Force }\"", shell=True)

env = os.environ.copy()
env["PROMETHEUS_URL"] = "http://localhost:9999"
p1 = subprocess.Popen(["python", "-m", "uvicorn", "app.main:app", "--port", "8000"], env=env)
time.sleep(3)

r = requests.post(f"{BACKEND_URL}/detection/run")
print("POST /detection/run (bad prom):", r.status_code, r.json())
p1.kill()

print("\n--- Step 11: Background polling loop ---")
env = os.environ.copy()
env["DETECTION_POLL_INTERVAL_SECONDS"] = "5"
p2 = subprocess.Popen(["python", "-m", "uvicorn", "app.main:app", "--port", "8000"], env=env)
time.sleep(3)
requests.post(f"{SIMULATOR_URL}/simulate/bad-deployment")

# Generate traffic so prometheus has metrics to be polled by the bg loop
end_time = time.time() + 75
while time.time() < end_time:
    try:
        requests.get(f"{SIMULATOR_URL}/api/checkout", timeout=1.0)
        requests.post(f"{SIMULATOR_URL}/webhook/payment-event", json={}, timeout=1.0)
    except Exception:
        pass
    time.sleep(0.5)

# Wait a little for bg loop to poll
time.sleep(6) 
r = requests.get(f"{BACKEND_URL}/incidents?status=open")
print("GET /incidents?status=open (after bg loop):", [i.get("id") for i in r.json()])

print("\n--- Step 12: Cooldown behavior ---")
open_incidents = r.json()
# Resolution via SQLite
for inc in open_incidents:
    idx = inc['id']
    subprocess.run(f"python -c \"from app.db import SessionLocal; from app.models import Incident; import datetime; db = SessionLocal(); inc = db.query(Incident).filter(Incident.id == {idx}).first(); inc.status = 'resolved'; inc.resolved_at = datetime.datetime.utcnow(); db.commit();\"", shell=True)

print("DB marked resolved.")
r = requests.post(f"{BACKEND_URL}/detection/run")
print("POST /detection/run (during cooldown):", r.json())

print("\n--- Step 13: Reset simulator ---")
requests.post(f"{SIMULATOR_URL}/simulate/reset")

# Also dump all incidents to a file so we can copy them into the report easily
res = requests.get(f"{BACKEND_URL}/incidents")
with open("test_incidents_dump.json", "w") as f:
    json.dump(res.json(), f, indent=2)

