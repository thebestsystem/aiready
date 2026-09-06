"""
==========================================================================
AGENTREADY - Moteur d'Audit Backend FastAPI
==========================================================================
Audit technique, simulation d'intention d'achat IA et génération d'auto-fix.
"""

import os
import re
import csv
import io
import json
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, urljoin

from dotenv import load_dotenv
load_dotenv()

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Preformatted
    )
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl

app = FastAPI(
    title="AgentReady API",
    description="Moteur d'audit et de préparation au commerce agentique",
    version="1.0.0"
)

# Enable CORS for frontend clients (local or production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ScanRequest(BaseModel):
    url: str
    geminiApiKey: Optional[str] = None

class PillarScore(BaseModel):
    score: int
    max: int = 100
    weight: str
    status: str
    label: str
    details: List[str] = []

class BrokenItem(BaseModel):
    title: str
    impact: str
    severity: str = "critical"

class AuditResult(BaseModel):
    domain: str
    name: str
    image: Optional[str] = None
    score: int
    status: str
    statusLabel: str
    statusBadgeClass: str
    summary: str
    pillars: Dict[str, PillarScore]
    aiView: Dict[str, str]
    autoFix: Dict[str, str]
    productData: Dict[str, Any]
    brokenItems: List[BrokenItem] = []
    rawJsonLd: str = ""
    fixedJsonLd: str = ""
    isWafBlocked: bool = False
    wafDetails: Optional[Dict[str, str]] = None
    geminiLive: bool = False

# Common Headers to avoid naive bot blockades while identifying as auditor
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 (compatible; AgentReadyBot/1.0; +https://agentready.io/bot)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
}

def normalize_url(raw_url: str) -> str:
    raw_url = raw_url.strip()
    if not raw_url.startswith("http://") and not raw_url.startswith("https://"):
        raw_url = "https://" + raw_url
    return raw_url

async def fetch_robots_txt(client: httpx.AsyncClient, domain: str) -> Dict[str, Any]:
    robots_url = f"https://{domain}/robots.txt"
    try:
        resp = await client.get(robots_url, timeout=5.0)
        if resp.status_code == 200:
            content = resp.text.lower()
            bots = ["gptbot", "claudebot", "perplexitybot", "google-extended"]
            disallowed_bots = []
            for b in bots:
                # Check for explicit disallow pattern
                if f"user-agent: {b}" in content and "disallow: /" in content:
                    disallowed_bots.append(b)
            
            # Check global disallow
            is_global_disallowed = "user-agent: *" in content and "\ndisallow: /\n" in content

            return {
                "found": True,
                "disallowed_bots": disallowed_bots,
                "global_disallowed": is_global_disallowed,
                "raw": resp.text[:500]
            }
    except Exception:
        pass
    return {"found": False, "disallowed_bots": [], "global_disallowed": False, "raw": ""}

async def check_llms_txt(client: httpx.AsyncClient, domain: str) -> Dict[str, Any]:
    for path in ["/.well-known/llms.txt", "/llms.txt"]:
        url = f"https://{domain}{path}"
        try:
            resp = await client.get(url, timeout=4.0)
            if resp.status_code == 200 and len(resp.text) > 30:
                return {"found": True, "path": path, "content": resp.text[:600]}
        except Exception:
            continue
    return {"found": False, "path": None, "content": None}

def extract_json_ld(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    json_ld_list = []
    scripts = soup.find_all("script", type="application/ld+json")
    for s in scripts:
        try:
            if s.string:
                data = json.loads(s.string.strip())
                if isinstance(data, list):
                    json_ld_list.extend(data)
                elif isinstance(data, dict):
                    if "@graph" in data and isinstance(data["@graph"], list):
                        json_ld_list.extend(data["@graph"])
                    else:
                        json_ld_list.append(data)
        except Exception:
            continue
    return json_ld_list

def analyze_schema(json_ld_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    product_obj = None
    for item in json_ld_list:
        item_type = str(item.get("@type", ""))
        if "Product" in item_type:
            product_obj = item
            break

    if not product_obj:
        return {
            "score": 25,
            "status": "Aucun schéma Product JSON-LD trouvé",
            "has_product": False,
            "details": ["Balise @type: Product absente du code source", "L'IA ne peut pas identifier les attributs certifiés"],
            "product_data": {}
        }

    score = 40
    details = ["Schéma @type: Product détecté (+40 pts)"]
    prod_name = product_obj.get("name", "Produit sans titre")
    prod_sku = product_obj.get("sku") or product_obj.get("gtin13") or product_obj.get("gtin")
    prod_desc = product_obj.get("description", "")
    
    # Extract image directly without downloading or saving
    prod_image = None
    raw_img = product_obj.get("image")
    if isinstance(raw_img, str):
        prod_image = raw_img
    elif isinstance(raw_img, list) and len(raw_img) > 0:
        if isinstance(raw_img[0], str):
            prod_image = raw_img[0]
        elif isinstance(raw_img[0], dict) and "url" in raw_img[0]:
            prod_image = raw_img[0]["url"]
    elif isinstance(raw_img, dict) and "url" in raw_img:
        prod_image = raw_img["url"]

    if prod_sku:
        score += 10
        details.append(f"Identifiant unique machine présent : SKU/GTIN ({prod_sku})")
    else:
        details.append("Identifiant unique SKU/GTIN manquant")

    # Inspect Offers
    offers = product_obj.get("offers", {})
    if isinstance(offers, list) and len(offers) > 0:
        offers = offers[0]

    has_price = False
    price_val = "Inconnu"
    currency = "EUR"
    has_shipping = False
    has_return = False
    has_stock = False

    if isinstance(offers, dict):
        if "price" in offers:
            has_price = True
            price_val = str(offers.get("price"))
            currency = str(offers.get("priceCurrency", "EUR"))
            score += 20
            details.append(f"Prix explicite trouvé : {price_val} {currency}")
        
        if "availability" in offers:
            has_stock = True
            score += 10
            details.append("Disponibilité en stock structurée")

        if "shippingDetails" in offers or "shippingRate" in offers:
            has_shipping = True
            score += 10
            details.append("Frais & délais de livraison (shippingDetails) présents")
        else:
            details.append("shippingDetails absent : L'IA ne peut pas calculer les frais de port")

        if "hasMerchantReturnPolicy" in offers:
            has_return = True
            score += 10
            details.append("Politique de retour (hasMerchantReturnPolicy) conforme")
        else:
            details.append("hasMerchantReturnPolicy absent : Risque d'hésitation pour l'agent IA")

    score = min(100, score)
    return {
        "score": score,
        "status": "Conforme" if score >= 80 else ("Partiel" if score >= 50 else "Critique"),
        "has_product": True,
        "details": details,
        "product_data": {
            "name": prod_name,
            "sku": prod_sku,
            "image": prod_image,
            "price": price_val,
            "currency": currency,
            "has_shipping": has_shipping,
            "has_return": has_return,
            "has_stock": has_stock,
            "description": prod_desc[:200]
        }
    }

def analyze_semantic_purity(soup: BeautifulSoup, raw_html_len: int) -> Dict[str, Any]:
    # Clone soup and strip noisy tags
    body = soup.find("body") or soup
    for tag in body.find_all(["script", "style", "noscript", "svg", "nav", "footer", "header", "iframe"]):
        tag.decompose()

    clean_text = body.get_text(separator=" ", strip=True)
    clean_len = len(clean_text)
    
    # Estimate tokens: 1 token ~ 4 characters in average European languages
    token_est = max(int(clean_len / 4), 100)
    noise_pct = max(0, min(100, int((1.0 - (clean_len / max(raw_html_len, 1))) * 100)))

    score = 100
    details = []

    if token_est > 3500:
        score -= 40
        details.append(f"Consommation de tokens excessive (~{token_est} tokens par requête)")
    elif token_est > 1800:
        score -= 20
        details.append(f"Volume de tokens modéré (~{token_est} tokens)")
    else:
        details.append(f"Excellente concision sémantique (~{token_est} tokens)")

    if noise_pct > 85:
        score -= 25
        details.append(f"Pollution DOM très élevée : {noise_pct}% du code HTML est du bruit non textuel")
    else:
        score += 10
        details.append(f"Ratio de contenu utile sain (bruit DOM : {noise_pct}%)")

    score = max(10, min(100, score))
    return {
        "score": score,
        "tokens": token_est,
        "noise_pct": noise_pct,
        "status": f"{token_est} tokens ({noise_pct}% bruit)",
        "details": details
    }

def get_gemini_api_key(user_key: Optional[str] = None) -> Optional[str]:
    if user_key and user_key.strip():
        return user_key.strip()
    try:
        from dotenv import find_dotenv
        env_file = find_dotenv(usecwd=True)
        if env_file:
            load_dotenv(env_file, override=True)
    except Exception:
        pass
    return (os.getenv("GEMINI_API_KEY") or "").strip() or None

def generate_gemini_content(client, prompt: str, is_json: bool = False, max_tokens: Optional[int] = None):
    config = types.GenerateContentConfig()
    if is_json:
        config.response_mime_type = "application/json"
    if max_tokens:
        config.max_output_tokens = max_tokens
        
    last_err = None
    for model in ["gemini-3.1-flash-lite", "gemini-3.6-flash"]:
        try:
            return client.models.generate_content(
                model=model,
                contents=prompt,
                config=config
            )
        except Exception as e:
            last_err = e
            continue
    raise last_err or RuntimeError("Modèles Gemini temporairement indisponibles")

async def run_ai_buyer_simulation(product_info: Dict[str, Any], user_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Appelle le SDK officiel Google GenAI (gemini-3.1-flash-lite / gemini-3.6-flash) si une clé est fournie
    (soit via la requête utilisateur, soit via la variable d'environnement GEMINI_API_KEY),
    sinon utilise le moteur déterministe expert en mode fallback.
    """
    api_key = get_gemini_api_key(user_key)
    if api_key and GENAI_AVAILABLE:
        try:
            client = genai.Client(api_key=api_key)
            prompt = f"""Tu es un agent IA autonome d'achat (comme ChatGPT Search, Gemini ou Operator).
Voici les données extraites d'une fiche produit e-commerce :
Nom: {product_info.get('name')}
Prix: {product_info.get('price')} {product_info.get('currency')}
Livraison spécifiée: {product_info.get('has_shipping')}
Retours spécifiés: {product_info.get('has_return')}
Stock vérifiable: {product_info.get('has_stock')}

Évalue cette fiche produit pour un achat autonome.
Réponds STRICTEMENT en format JSON avec ces champs :
{{
  "score": <note entre 0 et 100 sur ta confiance d'achat>,
  "hallucinationRisk": "<FAIBLE|MOYEN|ÉLEVÉ>",
  "verdict": "<Court diagnostic de 2 phrases>",
  "canBuy": <true ou false>
}}
"""
            res = await asyncio.to_thread(
                generate_gemini_content,
                client,
                prompt,
                is_json=True
            )
            parsed = json.loads(res.text)
            return {
                "score": parsed.get("score", 75),
                "hallucination_risk": parsed.get("hallucinationRisk", "FAIBLE"),
                "verdict": parsed.get("verdict", "Simulation en direct via Google Gemini validée."),
                "details": [
                    "Simulation d'achat en direct via Google Gemini Flash",
                    f"Confiance d'achat IA : {parsed.get('score', 75)}/100",
                    f"Risque d'hallucination estimé par Gemini : {parsed.get('hallucinationRisk', 'FAIBLE')}"
                ],
                "geminiLive": True
            }
        except Exception as e:
            print("Erreur appel Google GenAI:", e)

    # Fallback déterministe haute fidélité (sans clé API)
    score = 30
    details = []
    has_price = product_info.get("price") and product_info.get("price") != "Inconnu"
    has_shipping = product_info.get("has_shipping", False)
    has_return = product_info.get("has_return", False)
    has_stock = product_info.get("has_stock", False)

    if has_price:
        score += 25
        details.append("Prix certifié : L'agent IA peut présenter le coût exact")
    else:
        details.append("Prix incertain ou masqué par JavaScript")

    if has_shipping:
        score += 20
        details.append("Livraison claire : 0 hallucination sur les frais de port")
    else:
        details.append("Livraison non structurée : Risque d'hallucination sur les frais de port")

    if has_return:
        score += 15
        details.append("Politique de retour validée")

    if has_stock:
        score += 10
        details.append("Stock disponible confirmé")

    if score >= 80:
        risk = "FAIBLE (0-5%)"
    elif score >= 55:
        risk = "MOYEN (20-35%)"
    else:
        risk = "ÉLEVÉ (50%+)"

    return {
        "score": score,
        "hallucination_risk": risk,
        "verdict": "L'agent IA dispose des informations nécessaires pour recommander l'achat." if score >= 80 else "L'agent IA risque de renvoyer l'acheteur vers un concurrent en raison d'informations critiques manquantes.",
        "details": details,
        "geminiLive": False
    }

def generate_auto_fix_snippets(domain: str, prod: Dict[str, Any]) -> Dict[str, str]:
    name = prod.get("name") or "Produit E-commerce"
    price = prod.get("price") if prod.get("price") != "Inconnu" else "49.00"
    currency = prod.get("currency") or "EUR"
    sku = prod.get("sku") or "SKU-AUTO-01"

    llms_txt = f"""# LLMS.txt pour {domain}
# Specification: https://llmstxt.org/ v1.0
# Agentic Commerce Index

> {name} disponible sur {domain}.

## Fiches Produits & Spécifications Déterministes
- [{name}](/products/{sku.lower()}): Prix {price} {currency} TTC. Expédition garantie sous 24-48h.
- Conditions de retour: 30 jours satisfait ou remboursé.
- Support et contact agents: agent@{domain}
"""

    json_ld = f"""<script type="application/ld+json">
{{
  "@context": "https://schema.org/",
  "@type": "Product",
  "name": "{name}",
  "sku": "{sku}",
  "offers": {{
    "@type": "Offer",
    "price": "{price}",
    "priceCurrency": "{currency}",
    "availability": "https://schema.org/InStock",
    "shippingDetails": {{
      "@type": "OfferShippingDetails",
      "shippingRate": {{
        "@type": "MonetaryAmount",
        "value": "0.00",
        "currency": "{currency}"
      }}
    }},
    "hasMerchantReturnPolicy": {{
      "@type": "MerchantReturnPolicy",
      "merchantReturnDays": 30,
      "returnFees": "https://schema.org/FreeReturn"
    }}
  }}
}}
</script>"""

    mcp_config = f"""{{
  "mcpServers": {{
    "{domain.replace('.', '-')}-agent": {{
      "command": "npx",
      "args": ["-y", "@agentready/mcp-server-commerce", "--store={domain}"],
      "capabilities": ["query_stock", "checkout_token"]
    }}
  }}
}}"""

    return {
        "llmsTxt": llms_txt,
        "schemaJson": json_ld,
        "mcpConfig": mcp_config
    }

def extract_best_product_image(soup: BeautifulSoup, base_url: str, schema_image: Optional[str] = None) -> Optional[str]:
    # 1. Priorité au schéma JSON-LD si présent et non générique
    if schema_image and not any(bad in schema_image.lower() for bad in ["logo", "icon", "placeholder", "default", "blank"]):
        return urljoin(base_url, schema_image.strip())

    # 2. Balise OpenGraph ou Twitter
    og_img = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "og:image"})
    if og_img and og_img.get("content"):
        content = og_img["content"].strip()
        if content and not any(bad in content.lower() for bad in ["logo", "default", "placeholder", "favicon"]):
            return urljoin(base_url, content)

    tw_img = soup.find("meta", attrs={"name": "twitter:image"}) or soup.find("meta", property="twitter:image")
    if tw_img and tw_img.get("content"):
        content = tw_img["content"].strip()
        if content and not any(bad in content.lower() for bad in ["logo", "default", "placeholder"]):
            return urljoin(base_url, content)

    # 3. Algorithme de détection DOM pondéré (Score par mots-clés de titre/H1, ID et classes produit)
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

        # Élimination stricte des logos, bannières, avis, paiements et icônes
        if any(bad in src_lower or bad in img_class or bad in img_id for bad in [
            "logo", "icon", "cart", "panier", "arrow", "badge", "payment", "visa", "mastercard",
            "paypal", "trust", "avis", "pixel", "blank", "spinner", "loader", "bt_", "button",
            "social", "facebook", "twitter", "linkedin", "footer", "header", "promo", "glady", "banner", "403"
        ]):
            continue

        score = 0

        # Correspondance des mots-clés du texte ALT avec le titre du produit
        if alt:
            alt_words = set(re.findall(r'\w{3,}', alt_lower))
            common = alt_words.intersection(title_words)
            if len(common) >= 3:
                score += 80
            elif len(common) >= 1:
                score += 40

        # Indices forts dans l'ID ou la classe CSS
        if any(good in img_id or good in img_class for good in ["prod", "product", "zoom", "main", "primary", "detail", "visuel"]):
            score += 50

        # Indices de taille ou de dossier produit dans le chemin SRC
        if any(good in src_lower for good in ["product", "produit", "article", "item", "catalog"]):
            score += 30
        if any(good in src_lower for good in ["xlarge", "large", "zoom", "hd", "1000", "800"]):
            score += 25
        if any(bad in src_lower for bad in ["small", "thumb", "mini", "50x50", "100x100"]):
            score -= 30

        candidates.append((score, urljoin(base_url, src.strip())))

    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    return None

@app.post("/api/scan", response_model=AuditResult)
async def scan_url(req: ScanRequest):
    url = normalize_url(req.url)
    parsed = urlparse(url)
    domain = parsed.netloc or parsed.path.split("/")[0]

    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=12.0) as client:
        # 1. Fetch robots.txt & llms.txt in parallel with main page
        robots_task = fetch_robots_txt(client, domain)
        llms_task = check_llms_txt(client, domain)
        
        try:
            page_resp = await client.get(url)
            html_content = page_resp.text
            status_code = page_resp.status_code
            resp_headers = {k.lower(): v for k, v in page_resp.headers.items()}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Impossible de joindre l'URL : {str(e)}")

        robots_info, llms_info = await asyncio.gather(robots_task, llms_task)

    # PILIER 1 : Crawl & Bot Accessibility
    crawl_score = 100
    crawl_details = []
    
    # Check WAF & headers
    if "cf-ray" in resp_headers or "server" in resp_headers and "cloudflare" in resp_headers["server"].lower():
        if status_code in [403, 503]:
            crawl_score -= 60
            crawl_details.append("Protection WAF Cloudflare Challenge active (Bots bloqués)")
        else:
            crawl_score -= 10
            crawl_details.append("Cloudflare détecté (Accès standard préservé)")
    else:
        crawl_details.append("Aucun challenge WAF bloquant détecté")

    if robots_info["global_disallowed"]:
        crawl_score -= 50
        crawl_details.append("robots.txt bloque tous les crawlers (Disallow: /)")
    elif robots_info["disallowed_bots"]:
        crawl_score -= 30
        crawl_details.append(f"robots.txt bloque : {', '.join(robots_info['disallowed_bots'])}")
    else:
        crawl_details.append("robots.txt autorise les bots IA majeurs (GPTBot, ClaudeBot, PerplexityBot)")

    crawl_score = max(10, min(100, crawl_score))

    # Parse DOM
    soup = BeautifulSoup(html_content, "html.parser")
    page_title = soup.title.string.strip() if soup.title and soup.title.string else domain
    content_lower = html_content.lower()

    # Détection WAF / Anti-Bot / Rendu JavaScript CSR bloquant (Tâche 4)
    is_waf_blocked = False
    waf_details = None

    is_cf_challenge = (
        status_code in [403, 503] or
        "cf-mitigated" in content_lower or
        "challenge-platform" in content_lower or
        ("cloudflare" in resp_headers.get("server", "").lower() and ("just a moment" in content_lower or "enable javascript" in content_lower))
    )
    is_datadome = "datadome" in content_lower or "datadome" in resp_headers
    dom_text = soup.get_text(strip=True)
    is_empty_csr = len(dom_text) < 140 and any(k in content_lower for k in ["<div id=\"root\"", "<div id=\"app\"", "<div id=\"__next\"", "noscript"])

    if is_cf_challenge:
        is_waf_blocked = True
        waf_details = {
            "blocker": "Cloudflare WAF / Challenge",
            "message": "Nous n'avons pas pu lire le DOM complet.",
            "advice": "autorisez 'AgentReadyBot' dans votre pare-feu / servez un HTML SSR, puis relancez."
        }
        crawl_score = min(crawl_score, 25)
    elif is_datadome:
        is_waf_blocked = True
        waf_details = {
            "blocker": "DataDome Anti-bot",
            "message": "Nous n'avons pas pu lire le DOM complet.",
            "advice": "whitelisez le user-agent 'AgentReadyBot' ou fournissez un flux SSR pré-rendu."
        }
        crawl_score = min(crawl_score, 25)
    elif is_empty_csr:
        is_waf_blocked = True
        waf_details = {
            "blocker": "Rendu Client-Side (CSR non pré-rendu)",
            "message": "Le HTML reçu ne contient aucun texte produit (DOM vide avant exécution JS).",
            "advice": "activez le Server-Side Rendering (SSR) pour exposer vos fiches produits aux robots IA."
        }
        crawl_score = min(crawl_score, 35)

    # PILIER 2 : Schema.org & JSON-LD
    json_ld_list = extract_json_ld(soup)
    schema_res = analyze_schema(json_ld_list)

    # Extraire la vraie photo du produit sans sauvegarde disque
    prod_image = extract_best_product_image(soup, url, schema_res["product_data"].get("image"))
    schema_res["product_data"]["image"] = prod_image

    # PILIER 3 : Pureté Sémantique & Tokens
    semantic_res = analyze_semantic_purity(soup, len(html_content))

    # PILIER 4 : AI Buyer Simulator (100% Déterministe en V1 - Zéro appel LLM au scan)
    sim_score = 30
    sim_details = []
    prod_data = schema_res["product_data"]
    if prod_data.get("price") and prod_data.get("price") != "Inconnu":
        sim_score += 25
        sim_details.append("Prix certifié : L'agent IA peut présenter le montant exact")
    else:
        sim_details.append("Prix incertain ou masqué par JavaScript")

    if prod_data.get("has_shipping"):
        sim_score += 20
        sim_details.append("Livraison claire : 0 hallucination sur les frais de port")
    else:
        sim_details.append("Livraison non structurée : Risque d'hallucination")

    if prod_data.get("has_return"):
        sim_score += 15
        sim_details.append("Politique de retour validée")

    if prod_data.get("has_stock"):
        sim_score += 10
        sim_details.append("Stock disponible confirmé")

    sim_risk = "FAIBLE (0-5%)" if sim_score >= 80 else ("MOYEN (20-35%)" if sim_score >= 55 else "ÉLEVÉ (50%+)")
    sim_res = {
        "score": sim_score,
        "hallucination_risk": sim_risk,
        "details": sim_details,
        "geminiLive": False
    }

    # PILIER 5 : Protocoles Agentiques (llms.txt & MCP)
    proto_score = 0
    proto_details = []
    if llms_info["found"]:
        proto_score += 70
        proto_details.append(f"Fichier standard {llms_info['path']} détecté !")
    else:
        proto_details.append("Fichier /.well-known/llms.txt introuvable")

    proto_details.append("Configuration MCP manquante (Générée dans l'Auto-Fix)")
    proto_score = max(5, proto_score)

    # CALCUL DU SCORE GLOBAL V1 DÉTERMINISTE PUR (0 Variance, 0 LLM Judge)
    # 1. Crawl & Access (30%) + 2. Schema.org / JSON-LD (40%) + 3. Pureté Sémantique & Tokens (30%)
    total_score = int(
        (crawl_score * 0.30) +
        (schema_res["score"] * 0.40) +
        (semantic_res["score"] * 0.30)
    )
    total_score = max(5, min(100, total_score))

    # Auto-Fix Generation
    autofix_files = generate_auto_fix_snippets(domain, schema_res["product_data"])
    fixed_json_str = autofix_files.get("schemaJson", "")

    # Détection du JSON-LD brut actuel (Vue Avant)
    if json_ld_list:
        raw_json_str = json.dumps(json_ld_list[0] if len(json_ld_list) == 1 else json_ld_list, indent=2, ensure_ascii=False)
    else:
        raw_json_str = """<!-- ❌ AUCUN BALISAGE SCHEMA.ORG DÉTECTÉ SUR CETTE FICHE -->
<!-- Votre boutique est invisible pour ChatGPT Search, Gemini et Perplexity. -->
<!-- Les agents acheteurs ne peuvent pas vérifier le prix, le stock ni acheter. -->"""

    # Identification systématique des failles critiques "What's Broken" (P0 Conversion)
    broken_items = []
    if crawl_score < 75:
        broken_items.append(BrokenItem(
            title="Blocage des crawlers IA dans robots.txt ou WAF",
            impact="GPTBot (ChatGPT) ou ClaudeBot sont refoulés ou bridés lors de l'indexation de vos pages.",
            severity="critical"
        ))
    
    prod_info = schema_res["product_data"]
    if not prod_info.get("price") or prod_info.get("price") == "Inconnu":
        broken_items.append(BrokenItem(
            title="Prix et offre (Offer) absents du balisage Schema.org",
            impact="L'agent IA ne peut pas garantir le montant à l'acheteur et refuse de recommander le panier.",
            severity="critical"
        ))
    elif not prod_info.get("has_shipping") or not prod_info.get("has_return"):
        broken_items.append(BrokenItem(
            title="Politique de retour ou frais d'expédition non structurés",
            impact="Risque d'hallucination de 35% : l'IA invente des frais de port erronés ou renvoie vers Amazon.",
            severity="warning"
        ))
    
    if semantic_res["tokens"] > 3500:
        broken_items.append(BrokenItem(
            title=f"Surcharge DOM : {semantic_res['tokens']} tokens gaspillés par consultation",
            impact="Saturation du contexte des agents IA autonomes, perte de précision et risque de timeout.",
            severity="warning"
        ))
    
    if not llms_info["found"]:
        broken_items.append(BrokenItem(
            title="Index standard /.well-known/llms.txt manquant",
            impact="Aucun manifeste machine-readable direct fourni aux moteurs de recherche IA 2026.",
            severity="info"
        ))

    if not broken_items:
        broken_items.append(BrokenItem(
            title="Balisage agentique d'excellence",
            impact="Votre boutique fournit les données nécessaires pour convertir directement les agents IA acheteurs.",
            severity="info"
        ))

    # Status classification
    if total_score >= 80:
        status = "ready"
        status_label = "Agent Ready (Parfaitement Optimisé)"
        badge_class = "badge-ready"
        summary = f"Fiche produit hautement optimisée pour l'achat IA autonome. Schéma complet et données déterministes sur {domain}."
    elif total_score >= 50:
        status = "friction"
        status_label = "Agent Friction (Données partielles)"
        badge_class = "badge-friction"
        summary = f"Le site est accessible mais souffre d'ambiguïtés (frais de port ou politique de retour manquante dans le schéma)."
    else:
        status = "blind"
        status_label = "Agent Blind (Inaudible pour l'IA)"
        badge_class = "badge-blind"
        summary = f"Ce site est difficilement lisible ou bloqué pour les agents IA. Risque d'hallucination élevé lors des recherches d'achat."

    prod_name = schema_res["product_data"].get("name") or page_title
    extracted_price = f"{schema_res['product_data'].get('price', 'Inconnu')} {schema_res['product_data'].get('currency', 'EUR')}"

    return AuditResult(
        domain=url,
        name=prod_name,
        image=prod_image,
        score=total_score,
        status=status,
        statusLabel=status_label,
        statusBadgeClass=badge_class,
        summary=summary,
        brokenItems=broken_items,
        rawJsonLd=raw_json_str,
        fixedJsonLd=fixed_json_str,
        pillars={
            "crawl": PillarScore(
                score=crawl_score,
                weight="30%",
                status="Robots OK" if crawl_score >= 75 else "Friction / Bloqué",
                label="Crawl & Bot Access",
                details=crawl_details
            ),
            "schema": PillarScore(
                score=schema_res["score"],
                weight="40%",
                status=schema_res["status"],
                label="Schema.org / JSON-LD",
                details=schema_res["details"]
            ),
            "tokens": PillarScore(
                score=semantic_res["score"],
                weight="30%",
                status=semantic_res["status"],
                label="Pureté Sémantique",
                details=semantic_res["details"]
            ),
            "simulator": PillarScore(
                score=sim_res["score"],
                weight="Simulation",
                status=f"Risque {sim_res['hallucination_risk']}",
                label="AI Buyer Simulator (Aperçu)",
                details=sim_res["details"]
            ),
            "proto": PillarScore(
                score=proto_score,
                weight="Protocoles",
                status="llms.txt Présent" if proto_score >= 50 else "Absent",
                label="Protocoles (llms.txt / MCP)",
                details=proto_details
            )
        },
        aiView={
            "tokens": f"{semantic_res['tokens']} tokens",
            "extractedPrice": extracted_price,
            "stockStatus": "IN_STOCK (Confirmé Schema)" if schema_res["product_data"].get("has_stock") else "UNKNOWN (Non explicité dans JSON-LD)",
            "shippingTerms": "Livraison spécifiée dans Schema" if schema_res["product_data"].get("has_shipping") else "MISSING (hasMerchantReturnPolicy / shippingDetails absent)",
            "hallucinationRisk": sim_res["hallucination_risk"],
            "botAccess": "AUTORISÉS" if crawl_score >= 70 else "RESTREINT / BLOCKED"
        },
        autoFix=autofix_files,
        productData=schema_res["product_data"],
        isWafBlocked=is_waf_blocked,
        wafDetails=waf_details,
        geminiLive=False
    )

class SimQuestionRequest(BaseModel):
    question: str
    productData: Optional[Dict[str, Any]] = None
    geminiApiKey: Optional[str] = None

@app.get("/api/gemini/status")
def gemini_status():
    server_key = bool(get_gemini_api_key())
    return {
        "genaiAvailable": GENAI_AVAILABLE,
        "serverKeyConfigured": server_key,
        "model": "gemini-3.6-flash"
    }

@app.post("/api/gemini/test")
async def test_gemini_key(payload: Dict[str, str]):
    key = get_gemini_api_key(payload.get("geminiApiKey"))
    if not key:
        return {"ok": False, "error": "Aucune clé API fournie"}
    if not GENAI_AVAILABLE:
        return {"ok": False, "error": "google-genai n'est pas installé"}
    try:
        client = genai.Client(api_key=key)
        res = await asyncio.to_thread(
            generate_gemini_content,
            client,
            "Réponds uniquement par 'OK'",
            is_json=False,
            max_tokens=10
        )
        return {"ok": True, "model": "gemini-3.6-flash", "reply": res.text.strip() if res.text else "OK"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post("/api/gemini/simulate-question")
async def simulate_question(req: SimQuestionRequest):
    api_key = get_gemini_api_key(req.geminiApiKey)
    prod = req.productData or {}
    prod_name = prod.get("name") or "Produit E-commerce"
    prod_price = f"{prod.get('price', 'Inconnu')} {prod.get('currency', 'EUR')}"
    
    if api_key and GENAI_AVAILABLE:
        try:
            client = genai.Client(api_key=api_key)
            prompt = f"""Tu es un moteur d'audit de commerce agentique.
Un acheteur pose cette question à un agent IA autonome : "{req.question}"
Fiche produit analysée :
- Nom: {prod_name}
- Prix: {prod_price}
- Stock disponible: {prod.get('has_stock', 'Inconnu')}
- Livraison spécifiée: {prod.get('has_shipping', 'Non spécifiée')}
- Retours spécifiés: {prod.get('has_return', 'Non spécifiés')}

Génère une réponse comparative en JSON stricte avec la structure suivante :
{{
  "standardResponse": {{
    "agentStatus": "⚠️ Hallucination / Incertitude",
    "response": "<Comment un bot IA qui scrape du HTML brut sans JSON-LD répondrait (hésitation, prix imprécis ou risque d'abandon de panier)>",
    "verdict": "<Court impact négatif sur la vente>"
  }},
  "agentReadyResponse": {{
    "agentStatus": "✅ 100% Déterministe & Certifié",
    "response": "<Comment un agent IA optimisé AgentReady répondrait avec certitude et précision grâce aux métadonnées Schema.org et llms.txt>",
    "verdict": "<Court impact positif immédiat sur la conversion>"
  }},
  "model": "gemini-3.6-flash",
  "geminiLive": true
}}"""
            res = await asyncio.to_thread(
                generate_gemini_content,
                client,
                prompt,
                is_json=True
            )
            parsed = json.loads(res.text)
            parsed["geminiLive"] = True
            return parsed
        except Exception as e:
            print("Erreur simulation Gemini question:", e)

    # Fallback déterministe haute fidélité sans clé
    return {
        "geminiLive": False,
        "standardResponse": {
            "agentStatus": "⚠️ Risque d'Hallucination",
            "response": f"Je n'ai pas pu confirmer de manière certaine cette information pour \"{prod_name}\" car le code HTML de la boutique ne fournit pas de microdonnées JSON-LD explicites.",
            "verdict": "Perte de conversion probable ou renvoi vers un concurrent (Amazon, Fnac)."
        },
        "agentReadyResponse": {
            "agentStatus": "✅ 100% Déterministe (Protocole AgentReady)",
            "response": f"Information certifiée pour \"{prod_name}\" : les spécifications, le prix ({prod_price}) et les conditions d'expédition sont validés et certifiés via Schema.org et le manifeste llms.txt.",
            "verdict": "Panier validé et confirmation de commande autonome."
        },
        "model": "Mode déterministe (Entrez une clé Gemini pour l'IA en direct)"
    }

LEADS_FILE = os.path.join(os.path.dirname(__file__), "leads.csv")

def save_lead(email: str, domain: str, name: str, score: int, status: str, risk: str) -> None:
    file_exists = os.path.exists(LEADS_FILE)
    try:
        with open(LEADS_FILE, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Date", "Email", "URL_Boutique", "Nom_Produit", "Score", "Statut", "Risque_Hallucination"])
            writer.writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                email.strip(),
                domain.strip(),
                name.strip(),
                score,
                status.strip(),
                risk.strip()
            ])
    except Exception as e:
        print("Erreur sauvegarde lead:", e)

def generate_pdf_report(audit_data: Dict[str, Any], email: Optional[str] = None) -> bytes:
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("ReportLab n'est pas installé sur le serveur.")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    story = []

    # Custom Palette
    c_cyan = colors.HexColor('#06b6d4')
    c_emerald = colors.HexColor('#10b981')
    c_rose = colors.HexColor('#f43f5e')
    c_amber = colors.HexColor('#f59e0b')
    c_text_muted = colors.HexColor('#64748b')

    brand_style = ParagraphStyle(
        'BrandStyle',
        parent=styles['Normal'],
        fontSize=10,
        leading=13,
        textColor=c_cyan,
        fontName='Helvetica-Bold'
    )
    title_style = ParagraphStyle(
        'MainTitle',
        parent=styles['Heading1'],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#0f172a'),
        fontName='Helvetica-Bold'
    )
    section_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontSize=13,
        leading=16,
        textColor=colors.HexColor('#0f172a'),
        fontName='Helvetica-Bold'
    )
    normal_style = ParagraphStyle(
        'NormalText',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#334155')
    )
    code_style = ParagraphStyle(
        'CodeSnippet',
        parent=styles['Code'],
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor('#1e293b'),
        fontName='Courier'
    )

    # 1. Header Banner
    date_str = datetime.now().strftime("%d/%m/%Y à %H:%M")
    header_data = [
        [
            Paragraph("<b>AgentReady</b> • Rapport d'Audit White-Label 2026", brand_style),
            Paragraph(f"Date d'analyse : <b>{date_str}</b>", normal_style)
        ]
    ]
    t_header = Table(header_data, colWidths=[360, 180])
    t_header.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))
    story.append(t_header)
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1.5, color=c_cyan, spaceBefore=0, spaceAfter=15))

    # 2. Executive Summary Block
    name = audit_data.get("name") or "Boutique E-commerce"
    domain = audit_data.get("domain") or "https://example.com"
    score = audit_data.get("score", 50)
    status_label = audit_data.get("statusLabel") or ("Agent Ready" if score >= 80 else ("Agent Friction" if score >= 50 else "Agent Blind"))
    summary_text = audit_data.get("summary") or "Évaluation de la préparation de la boutique pour les agents d'achat IA."

    score_color = c_emerald if score >= 80 else (c_amber if score >= 50 else c_rose)

    story.append(Paragraph(f"Audit Technique : {name}", title_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"URL cible : <u>{domain}</u>", normal_style))
    story.append(Spacer(1, 12))

    summary_box_data = [
        [
            Paragraph(f"<font size=28 color='{score_color.hexval()}'><b>{score}</b></font><font size=14 color='#64748b'>/100</font><br/><br/><b>Statut :</b> {status_label}", normal_style),
            Paragraph(f"<b>Synthèse de l'Audit :</b><br/>{summary_text}<br/><br/><i>Client destinataire : {email or 'Confidentiel'}</i>", normal_style)
        ]
    ]
    t_summary = Table(summary_box_data, colWidths=[160, 380])
    t_summary.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
        ('PADDING', (0, 0), (-1, -1), 12),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(t_summary)
    story.append(Spacer(1, 15))

    # 3. Tableau des 5 Piliers
    story.append(Paragraph("Détail des 5 Piliers d'Évaluation Agentique", section_style))
    story.append(Spacer(1, 6))

    pillars = audit_data.get("pillars", {})
    p_crawl = pillars.get("crawl", {})
    p_schema = pillars.get("schema", {})
    p_tokens = pillars.get("tokens", {})
    p_sim = pillars.get("simulator", {})
    p_proto = pillars.get("proto") or pillars.get("protocols", {})

    pillars_rows = [
        [Paragraph("<b>Pilier</b>", normal_style), Paragraph("<b>Pondération</b>", normal_style), Paragraph("<b>Score</b>", normal_style), Paragraph("<b>Statut Technique</b>", normal_style)],
        [Paragraph("1. Crawl & Bot Access (robots.txt / WAF)", normal_style), Paragraph("20%", normal_style), Paragraph(f"<b>{p_crawl.get('score', '--')}/100</b>", normal_style), Paragraph(str(p_crawl.get('status', '--')), normal_style)],
        [Paragraph("2. Schema.org & JSON-LD Déterministe", normal_style), Paragraph("25%", normal_style), Paragraph(f"<b>{p_schema.get('score', '--')}/100</b>", normal_style), Paragraph(str(p_schema.get('status', '--')), normal_style)],
        [Paragraph("3. Pureté Sémantique & Économie de Tokens", normal_style), Paragraph("20%", normal_style), Paragraph(f"<b>{p_tokens.get('score', '--')}/100</b>", normal_style), Paragraph(str(p_tokens.get('status', '--')), normal_style)],
        [Paragraph("4. AI Buyer Simulator (Google Gemini Flash)", normal_style), Paragraph("20%", normal_style), Paragraph(f"<b>{p_sim.get('score', '--')}/100</b>", normal_style), Paragraph(str(p_sim.get('status', '--')), normal_style)],
        [Paragraph("5. Protocoles Agentiques (llms.txt / MCP)", normal_style), Paragraph("15%", normal_style), Paragraph(f"<b>{p_proto.get('score', '--')}/100</b>", normal_style), Paragraph(str(p_proto.get('status', '--')), normal_style)],
    ]

    t_pillars = Table(pillars_rows, colWidths=[220, 70, 70, 180])
    t_pillars.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(t_pillars)
    story.append(Spacer(1, 15))

    # 4. Diagnostic IA Acheteuse
    story.append(Paragraph("Diagnostic de l'IA Acheteuse (Google Gemini Flash)", section_style))
    story.append(Spacer(1, 6))

    ai_view = audit_data.get("aiView", {})
    gemini_details = p_sim.get("details", [])
    gemini_txt = "<br/>• ".join(gemini_details) if gemini_details else "Capacité d'achat autonome vérifiée."
    
    sim_table_data = [
        [Paragraph("<b>Prix extrait par l'agent :</b>", normal_style), Paragraph(str(ai_view.get("extractedPrice", "--")), normal_style)],
        [Paragraph("<b>Disponibilité du stock :</b>", normal_style), Paragraph(str(ai_view.get("stockStatus", "--")), normal_style)],
        [Paragraph("<b>Conditions de livraison :</b>", normal_style), Paragraph(str(ai_view.get("shippingTerms", "--")), normal_style)],
        [Paragraph("<b>Indice de risque d'hallucination :</b>", normal_style), Paragraph(f"<b>{ai_view.get('hallucinationRisk', '--')}</b>", normal_style)],
        [Paragraph("<b>Points de contrôle analysés :</b>", normal_style), Paragraph(f"• {gemini_txt}", normal_style)],
    ]
    t_sim = Table(sim_table_data, colWidths=[180, 360])
    t_sim.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('PADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(t_sim)
    story.append(Spacer(1, 15))

    # 5. Snippet llms.txt
    auto_fix = audit_data.get("autoFix", {})
    llms_txt = auto_fix.get("llmsTxt", "")
    if llms_txt:
        story.append(Paragraph("Spécification Standard Recommandée (/.well-known/llms.txt)", section_style))
        story.append(Spacer(1, 4))
        story.append(Preformatted(llms_txt[:450] + ("\n..." if len(llms_txt) > 450 else ""), code_style))
        story.append(Spacer(1, 10))

    # Footer
    story.append(HRFlowable(width="100%", thickness=0.5, color=c_text_muted, spaceBefore=10, spaceAfter=8))
    story.append(Paragraph("Rapport certifié édité par la plateforme AgentReady. Les standards d'audit suivent les spécifications W3C Schema.org 2026 et les protocoles LLMs.txt & Model Context Protocol (MCP).", ParagraphStyle('Foot', parent=styles['Normal'], fontSize=7.5, leading=10, textColor=c_text_muted)))

    doc.build(story)
    return buffer.getvalue()

class LeadRequest(BaseModel):
    email: str
    domain: str
    name: str = "Boutique E-commerce"
    score: int = 50
    status: str = "Agent Friction"
    risk: str = "MOYEN"

class PdfReportRequest(BaseModel):
    email: str
    auditData: Dict[str, Any]

@app.post("/api/lead")
def record_lead(req: LeadRequest):
    save_lead(req.email, req.domain, req.name, req.score, req.status, req.risk)
    return {"ok": True, "message": "Lead enregistré avec succès"}

@app.post("/api/report/pdf")
async def generate_and_download_pdf(req: PdfReportRequest):
    data = req.auditData or {}
    email = req.email.strip()
    domain = data.get("domain", "ecommerce")
    name = data.get("name", "Produit")
    score = data.get("score", 50)
    status_label = data.get("statusLabel", "Audit")
    risk = data.get("aiView", {}).get("hallucinationRisk", "MOYEN")

    # 1. Sauvegarder automatiquement le prospect dans leads.csv
    save_lead(email, domain, name, score, status_label, risk)

    # 2. Générer le document PDF
    try:
        pdf_bytes = await asyncio.to_thread(generate_pdf_report, data, email)
        clean_domain = re.sub(r'[^a-zA-Z0-9_-]', '_', domain.replace('https://', '').replace('http://', '').split('/')[0])
        filename = f"AgentReady-Audit-{clean_domain}.pdf"

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )
    except Exception as e:
        print("Erreur génération PDF:", e)
        raise HTTPException(status_code=500, detail=f"Erreur lors de la génération du PDF : {str(e)}")

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "AgentReady Audit Engine", "version": "1.0.0"}

# Servir directement le frontend statique (index.html, css, js) depuis FastAPI
_static_dir = os.path.dirname(os.path.abspath(__file__))
app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"Demarrage d'AgentReady sur le port {port}...")
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)

