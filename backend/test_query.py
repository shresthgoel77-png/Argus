import requests
import json

q_error = 'sum(rate(http_requests_total{job="simulator",status=~"5.."}[10m])) / sum(rate(http_requests_total{job="simulator"}[10m]))'
r = requests.get('http://localhost:9090/api/v1/query', params={'query': q_error})
print("Error query result:", json.dumps(r.json(), indent=2))

q_latency = 'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{job="simulator"}[30s])) by (le)) * 1000'
r2 = requests.get('http://localhost:9090/api/v1/query', params={'query': q_latency})
print("Latency query result:", json.dumps(r2.json(), indent=2))
