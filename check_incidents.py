import urllib.request
import json
try:
    res = urllib.request.urlopen("http://localhost:8000/detection/status") # or an incidents list endpoint
    print(res.read().decode())
except Exception as e:
    print(e)
