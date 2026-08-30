import sys
import os
import time
import json
import requests
os.environ["PROMETHEUS_URL"] = "http://127.0.0.1:9090"
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "backend")))

from app.detection import thresholds
from app.detection.detectors import detect_high_error_rate, detect_high_latency, detect_webhook_failure

SIMULATOR_URL = "http://localhost:9000"

def gen_traffic(seconds):
    end = time.time() + seconds
    while time.time() < end:
        try:
            requests.get(f"{SIMULATOR_URL}/api/checkout", timeout=5.0)
            requests.post(f"{SIMULATOR_URL}/webhook/payment-event", json={}, timeout=5.0)
        except requests.exceptions.RequestException:
            pass
        time.sleep(0.5)

output = {}
print("\n--- 1. RESET AND BASELINE ---")
requests.post(f"{SIMULATOR_URL}/simulate/reset")
gen_traffic(70)
output["baseline_err"] = detect_high_error_rate("simulator")
output["baseline_lat"] = detect_high_latency("simulator")
output["baseline_web"] = detect_webhook_failure("simulator")

print("\n--- 2. BAD DEPLOYMENT ---")
requests.post(f"{SIMULATOR_URL}/simulate/bad-deployment")
gen_traffic(70)
output["bad_err"] = detect_high_error_rate("simulator")
output["bad_lat"] = detect_high_latency("simulator")
output["bad_web"] = detect_webhook_failure("simulator")

print("\n--- 3. RECOVERY ---")
requests.post(f"{SIMULATOR_URL}/simulate/reset")
gen_traffic(75)
output["rec_err"] = detect_high_error_rate("simulator")
output["rec_lat"] = detect_high_latency("simulator")
output["rec_web"] = detect_webhook_failure("simulator")

print("\n--- 4. UNAVAILABLE PROMETHEUS ---")
os.environ["PROMETHEUS_URL"] = "http://localhost:9999"
try:
    detect_high_error_rate("simulator")
except Exception as e:
    output["propagate"] = f"{type(e).__name__} - {e}"

with open("verify_results.json", "w") as f:
    json.dump(output, f, indent=2)

