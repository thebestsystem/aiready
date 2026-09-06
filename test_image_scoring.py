import httpx
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin

url = "https://www.welcomeoffice.com/2644/1447620/65-evolve-jabra-te-jabra-ms-duo-casque-sans-fil-bluetooth-dongle-usb-a.aspx"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"
}

with httpx.Client(headers=headers, follow_redirects=True, timeout=15) as client:
    resp = client.get(url)
    print("Final URL:", resp.url, "Status:", resp.status_code)
    soup = BeautifulSoup(resp.text, "html.parser")
    page_title = soup.title.string.strip() if soup.title and soup.title.string else ""
    h1 = soup.find("h1")
    h1_text = h1.get_text(strip=True) if h1 else ""
    title_words = set(re.findall(r'\w{3,}', (page_title + " " + h1_text).lower()))

    candidates = []

    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-zoom-image") or img.get("data-original") or img.get("data-lazy")
        if not src:
            continue
        
        src_lower = src.lower()
        alt = (img.get("alt") or "").strip()
        alt_lower = alt.lower()
        img_id = (img.get("id") or "").lower()
        img_class = (" ".join(img.get("class", []))).lower()
        
        # Skip small icons/logos
        if any(bad in src_lower or bad in img_class or bad in img_id for bad in [
            "logo", "icon", "cart", "panier", "arrow", "badge", "payment", "visa", "mastercard",
            "paypal", "trust", "avis", "pixel", "blank", "spinner", "loader", "bt_", "button",
            "social", "facebook", "twitter", "linkedin", "footer", "header", "403"
        ]):
            continue
            
        score = 0
        
        # Alt text keyword match with page title / h1
        if alt:
            alt_words = set(re.findall(r'\w{3,}', alt_lower))
            common = alt_words.intersection(title_words)
            if len(common) >= 3:
                score += 80
            elif len(common) >= 1:
                score += 40

        # ID or Class clues
        if any(good in img_id or good in img_class for good in ["prod", "product", "zoom", "main", "primary", "detail"]):
            score += 50

        # SRC clues
        if any(good in src_lower for good in ["product", "produit", "article", "item", "catalog"]):
            score += 30
        if any(good in src_lower for good in ["xlarge", "large", "zoom", "hd", "1000", "800"]):
            score += 25
        if any(bad in src_lower for bad in ["small", "thumb", "mini", "50x50", "100x100"]):
            score -= 30

        candidates.append({
            "src": urljoin(str(resp.url), src),
            "score": score,
            "alt": alt[:40],
            "id": img_id,
            "class": img_class
        })

    candidates.sort(key=lambda x: x["score"], reverse=True)
    print("Top 5 candidates:")
    for c in candidates[:5]:
        print(f"Score {c['score']}: src={c['src']} (alt={c['alt']}, id={c['id']})")
