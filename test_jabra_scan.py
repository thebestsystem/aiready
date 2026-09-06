import urllib.request
import json

proxy_handler = urllib.request.ProxyHandler({})
opener = urllib.request.build_opener(proxy_handler)

url = "http://127.0.0.1:8000/api/scan"
target_url = "https://www.welcomeoffice.com/2644/1447620/65-evolve-jabra-te-jabra-ms-duo-casque-sans-fil-bluetooth-dongle-usb-a.aspx"
payload = json.dumps({"url": target_url}).encode("utf-8")
headers = {"Content-Type": "application/json"}

req = urllib.request.Request(url, data=payload, headers=headers)
try:
    with opener.open(req, timeout=20) as response:
        result = json.loads(response.read().decode("utf-8"))
        print("Product Title:", result.get("name"))
        print("Extracted Image URL:", result.get("image"))
        print("Score:", result.get("score"))
        print("Status:", result.get("statusLabel"))
except Exception as e:
    print("Error:", e)
