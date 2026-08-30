import subprocess
import time
import requests
import json

def run():
    print("Starting uvicorn server...")
    p = subprocess.Popen(
        ["python", "-m", "uvicorn", "simulator.app:app", "--port", "9000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    time.sleep(3)  # Wait for startup
    
    try:
        print("Running 20 consecutive checkout calls...")
        for i in range(20):
            r = requests.get("http://localhost:9000/api/checkout")
            assert r.status_code == 200, f"Expected 200, got {r.status_code}"
            
        print("Checking metrics endpoint...")
        r = requests.get("http://localhost:9000/metrics")
        assert r.status_code == 200, "Metrics failed"
        assert "http_requests_total" in r.text, "Metrics missing request counter"
        
        print("Validating app.log JSON lines...")
        with open("simulator/logs/app.log", "r") as f:
            lines = f.readlines()
            assert len(lines) >= 20, "Log lines missing"
            for line in lines:
                data = json.loads(line.strip())
                assert "timestamp" in data
                assert "endpoint" in data
                assert "status_code" in data
                assert "latency_ms" in data
                assert "request_id" in data
                
        print("ALL ACCEPTANCE CRITERIA PASSED!")
    finally:
        p.terminate()
        p.wait()

if __name__ == "__main__":
    run()
