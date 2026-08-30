import os
import sys
import json
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

# pyrefly: ignore [missing-import]
from app.observability.prometheus_client import instant_query, range_query, PrometheusUnavailableError
from app.observability.loki_client import query_range, LokiUnavailableError

def print_test(name): 
    print(f"\n--- {name} ---")

try:
    print_test("1. Verify instant_query('up') returns real Prometheus data, matching API contracts")
    res = instant_query("up")
    print("Type:", type(res))
    if len(res) > 0:
        print("Data[0]:", res[0])
    
    print_test("2. Verify range_query('http_requests_total') returns real simulator traffic datapoints")
    end = datetime.now(timezone.utc)
    start = end - timedelta(minutes=5)
    res_range = range_query("http_requests_total", start, end)
    print("Type:", type(res_range))
    if len(res_range) > 0:
        series = res_range[0]
        print("Metric labels:", series.get("metric"))
        # Print only first 3 points
        print(f"Values count: {len(series.get('values', []))}")
        print("First 2 values:", series.get("values", [])[:2])
    else:
        print("EMPTY RANGE_QUERY RESULT!")

    print_test("3. Verify Loki query_range('{job=\"simulator\"}') returns real simulator log entries")
    loki_res = query_range('{job="simulator"}', start, end)
    print("Type:", type(loki_res))
    if len(loki_res) > 0:
        print(f"Total lines: {len(loki_res)}")
        print("First log line dictionary keys:", list(loki_res[0].keys()))
        print("First log payload:", str(loki_res[0])[:150], "...")
    else:
        print("EMPTY LOKI LOG RESULT!")

    print_test("4. Verify invalid queries surface the service's actual error")
    try:
        instant_query("in&&&valid")
        print("FAIL: Did not raise exception")
    except PrometheusUnavailableError as e:
        print("Caught PrometheusUnavailableError:", e)
        
    print_test("5. Verify empty valid queries return []")
    empty_res = instant_query('up{job="NonExistentJob123"}')
    print("Result:", empty_res)

    print_test("6. Verify unreachable URLs raise error and do not hang/silently return []")
    import time
    
    # Prometheus unreachable
    os.environ["PROMETHEUS_URL"] = "http://localhost:9999"
    try:
        t0 = time.time()
        instant_query("up")
        print("FAIL: Prometheus did not raise")
    except PrometheusUnavailableError as e:
        print(f"PrometheusUnavailableError caught after {time.time()-t0:.2f}s:", e)
    
    # Loki unreachable
    os.environ["LOKI_URL"] = "http://localhost:9999"
    try:
        t0 = time.time()
        query_range('{job="simulator"}', start, end)
        print("FAIL: Loki did not raise")
    except LokiUnavailableError as e:
        print(f"LokiUnavailableError caught after {time.time()-t0:.2f}s:", e)
        
except Exception as main_e:
    print("UNEXPECTED ERROR:", main_e)
