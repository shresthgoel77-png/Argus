import urllib.request
import urllib.parse
import json

q = urllib.parse.quote('sum(rate(http_requests_total{job="simulator",status=~"5.."}[1m]))/sum(rate(http_requests_total{job="simulator"}[1m]))')
try:
    res = urllib.request.urlopen(f'http://localhost:9090/api/v1/query?query={q}')
    data = json.loads(res.read())
    print(json.dumps(data, indent=2))
except Exception as e:
    print(e)
