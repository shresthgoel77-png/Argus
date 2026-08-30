import subprocess
import time
import requests
import json
import os

cwd = r"C:\Users\HP\OneDrive\Desktop\.vscode\Argus\ai-reliability-engineer"

def git_cmd(*args):
    res = subprocess.run(["git"] + list(args), cwd=cwd, capture_output=True, text=True)
    return res.stdout.strip()

print("--- GIT START STATE ---")
print("HEAD:", git_cmd("rev-parse", "HEAD"))
print("STATUS:\n", git_cmd("status", "-s"))

print("\n--- STARTING SIMULATOR ---")
p = subprocess.Popen(["python", "-m", "uvicorn", "simulator.app:app", "--port", "9000"], cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(3) # Wait for uvicorn to boot

try:
    print("\n--- INITIAL STATE ---")
    resp = requests.get("http://127.0.0.1:9000/simulate/state")
    print("HTTP GET /simulate/state", resp.status_code)
    print(json.dumps(resp.json(), indent=2))

    print("\n--- POST /simulate/bad-deployment ---")
    resp = requests.post("http://127.0.0.1:9000/simulate/bad-deployment")
    print("HTTP POST", resp.status_code)
    data = resp.json()
    print(json.dumps(data, indent=2))
    
    print("\n--- GIT LOG AFTER BAD DEPLOYMENT ---")
    print(git_cmd("log", "-1", "--format=%H %s"))
    print("\n--- GIT STATUS AFTER BAD DEPLOYMENT ---")
    print(git_cmd("status", "-s"))
    
    print("\n--- SENDING 30 CHECKS TO /api/checkout ---")
    latencies = []
    errors = 0
    for _ in range(30):
        t1 = time.time()
        r = requests.get("http://127.0.0.1:9000/api/checkout")
        t2 = time.time()
        latencies.append((t2 - t1) * 1000)
        if r.status_code != 200:
            errors += 1
            
    avg_lat = sum(latencies)/len(latencies)
    print(f"Recorded avg latency: {avg_lat:.2f}ms")
    print(f"Recorded errors: {errors}/30")
    
    print("\n--- POST /simulate/bad-deployment (DUPLICATE) ---")
    resp = requests.post("http://127.0.0.1:9000/simulate/bad-deployment")
    print("HTTP POST", resp.status_code)
    print(json.dumps(resp.json(), indent=2))
    
    print("\n--- POST /simulate/reset ---")
    resp = requests.post("http://127.0.0.1:9000/simulate/reset")
    print("HTTP POST", resp.status_code)
    print(json.dumps(resp.json(), indent=2))
    
    print("\n--- GIT LOG AFTER RESET ---")
    print(git_cmd("log", "-1", "--format=%H %s"))
    
    print("\n--- CHECKOUT BEHAVIOR AFTER RESET ---")
    latencies = []
    errors = 0
    for _ in range(5):
        t1 = time.time()
        r = requests.get("http://127.0.0.1:9000/api/checkout")
        t2 = time.time()
        latencies.append((t2 - t1) * 1000)
        if r.status_code != 200:
            errors += 1
    avg_lat = sum(latencies)/len(latencies)
    print(f"Recorded avg latency (healthy): {avg_lat:.2f}ms")
    print(f"Recorded errors: {errors}/5")
    
    print("\n--- POST /simulate/reset (DUPLICATE) ---")
    resp = requests.post("http://127.0.0.1:9000/simulate/reset")
    print("HTTP POST", resp.status_code)
    print(json.dumps(resp.json(), indent=2))
    
    print("\n--- GIT END STATE ---")
    print("STATUS:\n", git_cmd("status", "-s"))

finally:
    p.terminate()
    p.wait()
