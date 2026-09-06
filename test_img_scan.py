import urllib.request
import json

proxy_handler = urllib.request.ProxyHandler({})
opener = urllib.request.build_opener(proxy_handler)

url = "http://127.0.0.1:8000/api/scan"
payload = json.dumps({"url": "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"}).encode("utf-8")
headers = {"Content-Type": "application/json"}

req = urllib.request.Request(url, data=payload, headers=headers)
try:
    with opener.open(req, timeout=15) as response:
        result = json.loads(response.read().decode("utf-8"))
        print("Product Title:", result.get("name"))
        print("Product Image URL Extracted:", result.get("image"))
        print("Score:", result.get("score"))
except Exception as e:
    print("Error:", e)
