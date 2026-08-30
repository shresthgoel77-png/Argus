import urllib.request
import urllib.error
import urllib.parse
try:
    req = urllib.request.Request("http://localhost:8000/detection/run", method="POST")
    res = urllib.request.urlopen(req)
    print("SUCCESS", res.read().decode())
except urllib.error.URLError as e:
    if hasattr(e, 'read'):
        print("ERROR:", e.read().decode())
    else:
        print("ERROR:", e)
