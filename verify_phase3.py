import subprocess
import time
import requests
import json
import os

cwd = r"C:\Users\HP\OneDrive\Desktop\.vscode\Argus\ai-reliability-engineer"

def pcmd(cmd_list):
    res = subprocess.run(cmd_list, cwd=cwd, capture_output=True, text=True)
    return res.stdout.strip()

print("\n--- DOCKER COMPOSE UP ---")
print(pcmd(["docker", "compose", "-f", "infrastructure/docker-compose.yml", "up", "-d"]))
time.sleep(3)

print("\n--- DOCKER PS ---")
print(pcmd(["docker", "ps", "--format", "table {{.Names}}\t{{.Status}}\t{{.Ports}}"]))

print("\n--- STARTING SIMULATOR ---")
sim_proc = subprocess.Popen(["python", "-m", "uvicorn", "simulator.app:app", "--port", "9000"], cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(5)  # Boot and Prom scrape once

PROMETHEUS_URL = "http://localhost:9090"
LOKI_URL = "http://localhost:3100"
SIMULATOR_URL = "http://localhost:9000"

try:
    print("\n--- PROMETHEUS TARGETS ---")
    try:
        resp = requests.get(f"{PROMETHEUS_URL}/api/v1/targets")
        targets = resp.json()["data"]["activeTargets"]
        for t in targets:
            if t["labels"].get("job") == "simulator":
                print(f"Target {t['scrapeUrl']} => {t['health']}")
    except Exception as e:
        print(f"Error fetching targets: {e}")

    print("\n--- METRICS BEFORE ---")
    try:
        resp = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": 'http_requests_total{endpoint="/api/checkout"}'})
        before_data = resp.json()
        val_before = sum(float(r["value"][1]) for r in before_data.get("data",{}).get("result",[]))
        print(f"Total /api/checkout requests: {val_before}")
    except Exception as e:
        print(f"Error fetching metrics: {e}")
        val_before = 0

    print("\n--- SENDING 5 CHECKS ---")
    for _ in range(5):
        requests.get(f"{SIMULATOR_URL}/api/checkout")
    
    print("Waiting 6 seconds for scrape...")
    time.sleep(6)

    print("\n--- METRICS AFTER ---")
    try:
        resp = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": 'http_requests_total{endpoint="/api/checkout"}'})
        after_data = resp.json()
        val_after = sum(float(r["value"][1]) for r in after_data.get("data",{}).get("result",[]))
        print(f"Total /api/checkout requests: {val_after}")
    except Exception as e:
        print(f"Error fetching metrics: {e}")

    print("\n--- LOKI LOGS ---")
    time.sleep(3) 
    try:
        resp = requests.get(f"{LOKI_URL}/loki/api/v1/query_range", params={"query": '{job="simulator"}'})
        loki_res = resp.json()
        streams = loki_res.get("data", {}).get("result", [])
        if streams:
            for s in streams:
                print("Stream:", s["stream"])
                print("Sample log line:", s["values"][-1][1])
        else:
            print("No Loki logs found")
    except Exception as e:
        print(f"Error fetching Loki logs: {e}")

    print("\n--- STOPPING LOKI ---")
    print(pcmd(["docker", "compose", "-f", "infrastructure/docker-compose.yml", "stop", "loki"]))

    print("\n--- SENDING REQUEST TO SIMULATOR WITHOUT LOKI ---")
    log_path = os.path.join(cwd, "simulator", "logs", "app.log")
    with open(log_path, "r") as f:
        file_len_before = len(f.readlines())
        
    t1 = time.time()
    resp = requests.get(f"{SIMULATOR_URL}/api/checkout")
    t2 = time.time()
    
    print(f"Status: {resp.status_code}, Latency: {(t2-t1)*1000:.2f}ms")
    with open(log_path, "r") as f:
        file_len_after = len(f.readlines())
        
    print(f"Log lines before: {file_len_before}, after: {file_len_after}")

finally:
    sim_proc.terminate()
    print("\n--- CLEANUP ---")
    print(pcmd(["docker", "compose", "-f", "infrastructure/docker-compose.yml", "down"]))
