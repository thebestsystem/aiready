import httpx
from bs4 import BeautifulSoup

url = "https://www.welcomeoffice.com/2644/1447620/65-evolve-jabra-te-jabra-ms-duo-casque-sans-fil-bluetooth-dongle-usb-a.aspx"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

with httpx.Client(headers=headers, follow_redirects=True, timeout=15) as client:
    resp = client.get(url)
    soup = BeautifulSoup(resp.text, "html.parser")
    
    # Check microdata (itemscope, itemtype, itemprop)
    itemscopes = soup.find_all(attrs={"itemscope": True})
    print("Itemscopes found:", len(itemscopes))
    for s in itemscopes:
        print("Itemtype:", s.get("itemtype"))
        itemprops = s.find_all(attrs={"itemprop": True})
        for p in itemprops[:8]:
            print(f"  itemprop {p.get('itemprop')}: {p.get('content') or p.get_text(strip=True)[:50]}")

    # Look for price elements
    print("\nPrice search:")
    for elem in soup.find_all(class_=lambda c: c and any(w in c.lower() for w in ["price", "prix", "amount"])):
        print(elem.get("class"), elem.get_text(strip=True)[:40])
