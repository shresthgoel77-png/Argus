import requests
import time
import sys

BACKEND_URL = "http://localhost:8000"
SIMULATOR_URL = "http://localhost:9000"

def generate_traffic(seconds):
    print(f"Generating traffic for {seconds} seconds...")
    end_time = time.time() + seconds
    while time.time() < end_time:
        try:
            requests.get(f"{SIMULATOR_URL}/api/checkout", timeout=3.0)
            requests.post(f"{SIMULATOR_URL}/webhook/payment-event", json={}, timeout=3.0)
        except:
            pass
        time.sleep(0.5)

def main():
    print("--- LIVE E2E REMEDIATION TEST ---")
    
    try:
        # 0. reset simulator
        requests.post(f"{SIMULATOR_URL}/simulate/reset")
        time.sleep(1)
        
        # 1. trigger bad deployment
        # To make sure detection picks it up, maybe sleep 1s
        resp = requests.post(f"{SIMULATOR_URL}/simulate/bad-deployment")
        resp.raise_for_status()
        print("Triggered bad deployment.")
        generate_traffic(70)
        
        # 2. detection
        resp = requests.post(f"{BACKEND_URL}/detection/run")
        resp.raise_for_status()
        detection_res = resp.json()
        
        incident_id = None
        if "new_incidents" in detection_res and len(detection_res["new_incidents"]) > 0:
            incident_id = detection_res["new_incidents"][0].get("id")
        
        if not incident_id:
            # wait a moment and try again if metrics haven't spiked
            time.sleep(2)
            resp = requests.post(f"{BACKEND_URL}/detection/run")
            resp.raise_for_status()
            detection_res = resp.json()
            if "new_incidents" in detection_res and len(detection_res["new_incidents"]) > 0:
                incident_id = detection_res["new_incidents"][0].get("id")
                
        if not incident_id:
            print("Failed to detect incident!")
            sys.exit(1)
            
        print(f"Detected incident {incident_id}.")
        
        # 3. Investigation
        resp = requests.post(f"{BACKEND_URL}/investigation/run/{incident_id}")
        resp.raise_for_status()
        print("Investigation run complete.")
        
        # 4. RCA
        resp = requests.post(f"{BACKEND_URL}/ai/rca/{incident_id}")
        resp.raise_for_status()
        print("RCA run complete.")
        
        # 5. Remediation Propose
        resp = requests.post(f"{BACKEND_URL}/remediation/propose/{incident_id}")
        resp.raise_for_status()
        propose_res = resp.json()
        action_id = propose_res["id"]
        print(f"Proposed remediation action {action_id}: {propose_res['action_type']} (status={propose_res['status']})")
        
        # 6. Duplicate propose -> 409
        resp = requests.post(f"{BACKEND_URL}/remediation/propose/{incident_id}")
        assert resp.status_code == 409, f"Expected 409, got {resp.status_code}"
        print("Checked duplicate proposal (409 correct).")
        
        # 7. Approve
        resp = requests.post(f"{BACKEND_URL}/remediation/{action_id}/approve", json={"approved_by": "e2e_tester"})
        resp.raise_for_status()
        print("Approved remediation action.")
        
        # 8. Double approve -> 409
        resp = requests.post(f"{BACKEND_URL}/remediation/{action_id}/approve", json={"approved_by": "e2e_tester2"})
        assert resp.status_code == 409, f"Expected 409, got {resp.status_code}"
        
        # 9. Reject -> 409 (since it's already approved)
        resp = requests.post(f"{BACKEND_URL}/remediation/{action_id}/reject", json={"rejected_by": "e2e_tester2"})
        assert resp.status_code == 409, f"Expected 409, got {resp.status_code}"
        print("Checked state machine transition blocks (409 correct).")
        
        # Clean up simulator
        requests.post(f"{SIMULATOR_URL}/simulate/reset")

        print("[SUCCESS] All live E2E validations passed.")
        sys.exit(0)

    except Exception as e:
        print(f"[ERROR] {e}")
        requests.post(f"{SIMULATOR_URL}/simulate/reset")
        sys.exit(1)

if __name__ == "__main__":
    main()
