import os
import time
import requests
import json
import subprocess

BACKEND_URL = "http://localhost:8000"
SIMULATOR_URL = "http://localhost:9000"

def generate_traffic(seconds: int):
    end_time = time.time() + seconds
    while time.time() < end_time:
        try:
            requests.get(f"{SIMULATOR_URL}/api/checkout", timeout=1.0)
            requests.post(f"{SIMULATOR_URL}/webhook/payment-event", json={}, timeout=1.0)
        except Exception:
            pass
        time.sleep(0.5)

print("\n=== STARTING CLEAN BACKEND ===")
subprocess.run("powershell -Command \"$pid_kill = (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue).OwningProcess; if ($pid_kill) { Stop-Process -Id $pid_kill -Force }\"", shell=True)
env = os.environ.copy()
env["DETECTION_POLL_INTERVAL_SECONDS"] = "3600"
env["PROMETHEUS_URL"] = "http://localhost:9090"
p = subprocess.Popen(["python", "-m", "uvicorn", "app.main:app", "--port", "8000"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(4)

print("\n--- 3. Reset and healthy traffic ---")
requests.post(f"{SIMULATOR_URL}/simulate/reset")
generate_traffic(70)
r = requests.post(f"{BACKEND_URL}/detection/run")
print(f"POST /detection/run (healthy): status={r.status_code} json={json.dumps(r.json())}")

print("\n--- 4/5. Trigger Bad Deployment & Detection ---")
requests.post(f"{SIMULATOR_URL}/simulate/bad-deployment")
generate_traffic(70)
res = requests.post(f"{BACKEND_URL}/detection/run")
data = res.json()
print("POST /detection/run (bad):", json.dumps(data, indent=2))

print("\n--- 6. Deduplication check (Immediate POST) ---")
r_dedup = requests.post(f"{BACKEND_URL}/detection/run")
print(f"POST /detection/run (dedup): status={r_dedup.status_code} json={json.dumps(r_dedup.json())}")

print("\n--- 7/8. GET /incidents ---")
open_incs = requests.get(f"{BACKEND_URL}/incidents?status=open").json()
print("GET /incidents?status=open length:", len(open_incs))
if open_incs:
    id = open_incs[0]["id"]
    single = requests.get(f"{BACKEND_URL}/incidents/{id}").json()
    print(f"GET /incidents/{id} returned id=", single.get("id"), "status=", single.get("status"))

print("\nCleaning up backend...")
p.kill()
