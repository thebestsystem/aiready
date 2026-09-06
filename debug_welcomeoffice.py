import httpx
from bs4 import BeautifulSoup
import json

url = "https://www.welcomeoffice.com/2644/1447620/65-evolve-jabra-te-jabra-ms-duo-casque-sans-fil-bluetooth-dongle-usb-a.aspx"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

with httpx.Client(headers=headers, follow_redirects=True, timeout=15) as client:
    resp = client.get(url)
    print("Status:", resp.status_code)
    soup = BeautifulSoup(resp.text, "html.parser")
    
    # Check JSON-LD
    json_lds = soup.find_all("script", type="application/ld+json")
    print("JSON-LD scripts found:", len(json_lds))
    for j in json_lds:
        try:
            d = json.loads(j.string.strip())
            print("JSON-LD sample:", json.dumps(d)[:200])
        except Exception as e:
            pass

    # Check OG Image
    og = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "og:image"})
    print("OG Image:", og.get("content") if og else None)

    # Check Twitter Image
    tw = soup.find("meta", attrs={"name": "twitter:image"}) or soup.find("meta", property="twitter:image")
    print("Twitter Image:", tw.get("content") if tw else None)

    # Find image with id or class containing product / zoom / main
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-zoom-image") or img.get("data-original")
        alt = img.get("alt", "")
        img_id = img.get("id", "")
        img_class = " ".join(img.get("class", []))
        if any(w in (alt + img_id + img_class + str(src)).lower() for w in ["jabra", "evolve", "product", "article", "visuel", "zoom", "1447620"]):
            print(f"Candidate img: src={src}, id={img_id}, class={img_class}, alt={alt[:40]}")
