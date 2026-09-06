import os
import urllib.request
import json

# Disable proxy for localhost
proxy_handler = urllib.request.ProxyHandler({})
opener = urllib.request.build_opener(proxy_handler)

url = "http://127.0.0.1:8000/api/scan"
payload = json.dumps({"url": "https://example.com"}).encode("utf-8")
headers = {"Content-Type": "application/json"}

req = urllib.request.Request(url, data=payload, headers=headers)
try:
    with opener.open(req, timeout=15) as response:
        result = json.loads(response.read().decode("utf-8"))
        print("SUCCESS! Status:", response.status)
        print("Score:", result.get("score"))
        print("Domain:", result.get("domain"))
        print("Summary:", result.get("summary"))
        print("Pillars:", list(result.get("pillars", {}).keys()))
except urllib.error.HTTPError as e:
    print("HTTP Error:", e.code, e.read().decode("utf-8"))
except Exception as e:
    print("Error:", type(e), e)
