import urllib.request
import json

proxy_handler = urllib.request.ProxyHandler({})
opener = urllib.request.build_opener(proxy_handler)

url = "http://127.0.0.1:8000/api/scan"
# Testing with an actual public website
payload = json.dumps({"url": "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"}).encode("utf-8")
headers = {"Content-Type": "application/json"}

req = urllib.request.Request(url, data=payload, headers=headers)
try:
    with opener.open(req, timeout=20) as response:
        result = json.loads(response.read().decode("utf-8"))
        print("=== SCAN SUCCESS ===")
        print("Product Name:", result.get("name"))
        print("Total Score:", result.get("score"), "/ 100")
        print("Status:", result.get("statusLabel"))
        print("Pillars:", {k: v.get("score") for k, v in result.get("pillars", {}).items()})
        print("AI View Tokens:", result.get("aiView", {}).get("tokens"))
        print("Auto-Fix llms.txt generated:\n", result.get("autoFix", {}).get("llmsTxt")[:180], "...")
except Exception as e:
    print("Error:", type(e), e)
