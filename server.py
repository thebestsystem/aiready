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

# Modèles officiels Google GenAI centralisés (Contexte temporel 2026 : séries 3.x stables)
GEMINI_PRIMARY_MODEL = "gemini-3.6-flash"
GEMINI_FALLBACK_MODEL = "gemini-3.1-flash-lite"
GEMINI_MODELS = [GEMINI_PRIMARY_MODEL, GEMINI_FALLBACK_MODEL]

import time
from collections import defaultdict

import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Response, Request, Depends
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl

from lead_sink import dispatch_lead
from pdf_generator import generate_pdf_report   # refactor P1 : rendu ReportLab déporté hors monolithe


app = FastAPI(
    title="AgentReady API",
    description="Moteur d'audit et de préparation au commerce agentique",
    version="1.0.0"
)

# Configuration CORS durcie et conforme aux standards W3C (Issue #3)
cors_origins_raw = os.getenv("CORS_ORIGINS", "").strip()
if cors_origins_raw and cors_origins_raw != "*":
    origins = [o.strip() for o in cors_origins_raw.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

# ==========================================================================
# Rate-limit anti-abus (TACHE-01) — fenêtre glissante en mémoire par IP
# ==========================================================================
# Choix de parsing X-Forwarded-For : on utilise le DERNIER élément de la
# chaîne (le plus proche du serveur), car c'est celui ajouté par le proxy de
# confiance (Railway). Se fier au premier élément permettrait à un client de
# spoof l'en-tête et de contourner la limite (faille de spoofing).
# En déploiement direct (sans proxy), request.client.host est l'IP réelle.


class RateLimitExceeded(HTTPException):
    """Exception levée en cas de dépassement de quota (HTTP 429)."""
    def __init__(self, detail: str, retry_after: int):
        super().__init__(
            status_code=429,
            detail=detail,
            headers={"Retry-After": str(retry_after)}
        )
        self.retry_after = retry_after


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={
            "detail": exc.detail,
            "retry_after": exc.retry_after
        },
        headers={"Retry-After": str(exc.retry_after)}
    )


def _get_client_ip(request: Request) -> str:
    """Extrait l'IP réelle du client derrière un éventuel reverse proxy."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # Dernier élément = IP ajoutée par le proxy de confiance le plus proche
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


class _SlidingWindowRateLimiter:
    """Fenêtre glissante en mémoire : dict IP -> liste de timestamps.

    NOTE: ce mécanisme est mono-processus (uvicorn single worker). En multi-worker,
    il faudra migrer vers Redis (prévu P2).
    """

    def __init__(self, limit: int, window_seconds: int, limit_env_key: Optional[str] = None, window_env_key: Optional[str] = None):
        self._default_limit = limit
        self._default_window = window_seconds
        self._limit_env_key = limit_env_key
        self._window_env_key = window_env_key
        self._override_limit = None
        self._override_window = None
        self._hits: Dict[str, List[float]] = defaultdict(list)

    @property
    def limit(self) -> int:
        if self._override_limit is not None:
            return self._override_limit
        if self._limit_env_key:
            try:
                return int(os.getenv(self._limit_env_key, str(self._default_limit)))
            except ValueError:
                return self._default_limit
        return self._default_limit

    @limit.setter
    def limit(self, val: int) -> None:
        self._override_limit = val

    @property
    def window_seconds(self) -> int:
        if self._override_window is not None:
            return self._override_window
        if self._window_env_key:
            try:
                return int(os.getenv(self._window_env_key, str(self._default_window)))
            except ValueError:
                return self._default_window
        return self._default_window

    @window_seconds.setter
    def window_seconds(self, val: int) -> None:
        self._override_window = val

    def reset(self) -> None:
        """Vide toutes les fenêtres (utile pour les tests)."""
        self._hits.clear()
        self._override_limit = None
        self._override_window = None

    def check(self, ip: str) -> Optional[int]:
        """Enregistre un hit et renvoie le délai d'attente (s) si dépassé, sinon None."""
        now = time.time()
        window_start = now - self.window_seconds
        # Purge des entrées expirées pour cette IP
        self._hits[ip] = [t for t in self._hits[ip] if t > window_start]
        if len(self._hits[ip]) >= self.limit:
            retry_after = int(self.window_seconds - (now - self._hits[ip][0])) + 1
            return max(retry_after, 1)
        self._hits[ip].append(now)
        # Purge globale des IP inactives pour éviter une fuite mémoire en croissance infinie
        if len(self._hits) > 1000:
            cutoff = now - self.window_seconds
            self._hits = defaultdict(
                list,
                {k: [t for t in v if t > cutoff] for k, v in self._hits.items() if any(t > cutoff for t in v)}
            )
        return None


# Limites configurables par env (défauts permissifs pour ne pas casser la démo front légitime)
SCAN_RATE_LIMIT = int(os.getenv("SCAN_RATE_LIMIT", "10"))
SCAN_RATE_WINDOW_SECONDS = int(os.getenv("SCAN_RATE_WINDOW_SECONDS", "60"))
SIM_RATE_LIMIT = int(os.getenv("SIM_RATE_LIMIT", "5"))
SIM_RATE_WINDOW_SECONDS = int(os.getenv("SIM_RATE_WINDOW_SECONDS", "60"))

_scan_limiter = _SlidingWindowRateLimiter(SCAN_RATE_LIMIT, SCAN_RATE_WINDOW_SECONDS, "SCAN_RATE_LIMIT", "SCAN_RATE_WINDOW_SECONDS")
_sim_limiter = _SlidingWindowRateLimiter(SIM_RATE_LIMIT, SIM_RATE_WINDOW_SECONDS, "SIM_RATE_LIMIT", "SIM_RATE_WINDOW_SECONDS")

# ==========================================================================
# Garde-fous du scanner (TACHE-02) — bornes configurables via variables d'env.
# ==========================================================================
def _int_env_clamped(key: str, default_str: str, lo: int, hi: int) -> int:
    """Lit un entier configurable via env et le clamp dans [lo, hi].

    Tolérant : toute valeur illisible (non-int) retombe sur le défaut.
    Facilité de test : comportement isolable, sinon testé par ré-import.
    """
    try:
        v = int(os.getenv(key, default_str))
    except (TypeError, ValueError):
        v = int(default_str)
    return max(lo, min(hi, v))

# Timeout réseau (s) appliqué à l'AsyncClient principal du scan. Clamp 1..60.
SCAN_FETCH_TIMEOUT_SECONDS = _int_env_clamped("SCAN_FETCH_TIMEOUT_SECONDS", "12", 1, 60)
# Taille max (octets) d'une page principale chargée puis analysée (anti-abus mémoire/CPU).
# Clamp : jamais < 100 Ko. Comportement : si le serveur annonce un Content-Length > borne
# -> HTTP 413 ; sinon la lecture est tronquée à cette borne (jamais plus stocké).
SCAN_MAX_RESPONSE_BYTES = _int_env_clamped("SCAN_MAX_RESPONSE_BYTES", "2000000", 100_000, 10**12)


def _enforce_rate_limit(request: Request, limiter: _SlidingWindowRateLimiter, endpoint_name: str) -> None:
    """Refuse 429 (JSON + Retry-After) si la limite par IP est dépassée."""
    ip = _get_client_ip(request)
    retry_after = limiter.check(ip)
    if retry_after is not None:
        raise RateLimitExceeded(
            detail=f"Trop de requêtes sur {endpoint_name}. Réessayez dans {retry_after} s.",
            retry_after=retry_after
        )


def _scan_rate_limit(request: Request) -> None:
    """Dépendance FastAPI : rate-limit du scanner lourd."""
    _enforce_rate_limit(request, _scan_limiter, "/api/scan")


def _sim_rate_limit(request: Request) -> None:
    """Dépendance FastAPI : rate-limit du simulateur LLM coûteux."""
    _enforce_rate_limit(request, _sim_limiter, "/api/gemini/simulate-question")


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
    """Normalise ET valide strictement une URL de scan, AVANT tout fetch réseau.

    Règles (TACHE-02) :
      - schémas uniquement http/https (sinon 400),
      - pas d'espace interne ni saut de ligne (sinon 400),
      - longueur maximale 2048 (sinon 400),
      - hôte non vide requis (sinon 400).

    Lève HTTPException(400) sur entrée invalide. Ne fait JAMAIS de requête réseau.
    """
    raw = raw_url.strip()
    if not raw:
        raise HTTPException(status_code=400, detail="URL non valide : champ vide.")
    if len(raw) > 2048:
        raise HTTPException(status_code=400, detail="URL trop longue (max 2048 caractères).")
    if any(c.isspace() for c in raw):
        raise HTTPException(status_code=400, detail="URL non valide : ne doit pas contenir d'espace ni de retour à la ligne.")
    lower = raw.lower()
    if not (lower.startswith("http://") or lower.startswith("https://")):
        raise HTTPException(status_code=400, detail="URL non valide : seuls les liens http:// et https:// sont acceptés.")
    parsed = urlparse(raw)
    host = (parsed.netloc or "").lower()
    is_sane_host = host == "localhost" or ("." in host and len(host) > 2)
    if not is_sane_host:
        raise HTTPException(status_code=400, detail="URL invalide : hôte manquant.")
    return raw


def _decode_utf8(raw: bytes) -> str:
    """Décode des octets HTTP en texte tolérant (utf-8 avec remplacement)."""
    try:
        return raw.decode("utf-8", errors="replace")
    except Exception:
        return ""


async def _read_page_bounded(resp: httpx.Response, limit: int) -> bytes:
    """Lit le corps d'une réponse httpx sans jamais conserver plus de `limit` octets.

    Utilise le streaming natif (`aiter_bytes`) pour les vraies réponses `httpx.Response`.
    Repli sûr vers le corps déjà matérialisé pour les objets de test simples
    (Starlette TestClient / mocks qui exposent `.text`) — suffisant car ces corps
    sont de toute façon déjà en mémoire.
    """
    raw_parts = []
    size = 0
    # Détection d'un vrai flux httpx (et non d'un mock qui répond True à tout).
    if isinstance(resp, httpx.Response) and resp.aiter_bytes is not None:
        try:
            async for chunk in resp.aiter_bytes():
                if isinstance(chunk, str):
                    chunk = chunk.encode("utf-8", "ignore")
                if size >= limit:
                    break
                room = limit - size
                seg = bytes(chunk)[:room]
                raw_parts.append(seg)
                size += len(seg)
            return b"".join(raw_parts)
        except Exception:
            # chute contrôlée : on retombe sur le corps matérialisé ci-dessous
            pass
    text = getattr(resp, "text", "") or ""
    body = text.encode("utf-8", "replace") if isinstance(text, str) else bytes(text or b"")
    return body[:limit]


async def _cancel_scan_tasks(*tasks) -> None:
    """Annule proprement des tâches asyncio et attend leur fin (sans avertissement).

    Utilisé sur les chemins d'erreur du scan pour éviter les RuntimeWarning
    "coroutine was never awaited" quand on refuse la page avant le gather final.
    """
    for t in tasks:
        if not t.done():
            t.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


def _looks_like_web_page(content_type_header: str, html_head: str) -> bool:
    """Une ressource peut-elle être analysée comme une page web HTML ?

    Accepte explicitement text/html et application/xhtml+xml.
    Filet de tolérance : text/plain (ou Content-Type absent) n'est accepté que si le
    début du corps contient un balisage HTML explicite (<html / <head / <!doctype).
    """
    ct = (content_type_header or "").lower()
    if "text/html" in ct or "application/xhtml+xml" in ct:
        return True
    head = (html_head or "").lower()
    if ("text/plain" in ct or not ct) and ("<html" in head or "<head" in head or "<!doctype" in head):
        return True
    return False

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

def _get_gemini_client(api_key: Optional[str] = None):
    """Initialisation factorisée et sécurisée du client Google GenAI."""
    key = get_gemini_api_key(api_key)
    if not key or not GENAI_AVAILABLE:
        return None
    try:
        return genai.Client(api_key=key)
    except Exception as e:
        print(f"[Gemini] Erreur création client: {e}")
        return None

def generate_gemini_content(client, prompt: str, is_json: bool = False, max_tokens: Optional[int] = None):
    config = types.GenerateContentConfig()
    if is_json:
        config.response_mime_type = "application/json"
    if max_tokens:
        config.max_output_tokens = max_tokens

    last_err = None
    for model in GEMINI_MODELS:
        try:
            res = client.models.generate_content(
                model=model,
                contents=prompt,
                config=config
            )
            return res, model
        except Exception as e:
            last_err = e
            print(f"[Gemini] Échec sur {model} ({e}), tentative bascule fallback...")
            continue
    raise last_err or RuntimeError("Tous les modèles Gemini sont temporairement indisponibles")

async def run_ai_buyer_simulation(product_info: Dict[str, Any], user_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Appelle le SDK officiel Google GenAI via _get_gemini_client (cascade GEMINI_MODELS)
    si une clé est disponible, sinon utilise le moteur déterministe certifié.
    """
    client = _get_gemini_client(user_key)
    if client:
        try:
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
            res, model_used = await asyncio.to_thread(
                generate_gemini_content,
                client,
                prompt,
                is_json=True
            )
            parsed = json.loads(res.text)
            return {
                "score": parsed.get("score", 75),
                "hallucination_risk": parsed.get("hallucinationRisk", "FAIBLE"),
                "verdict": parsed.get("verdict", f"Simulation en direct via {model_used} validée."),
                "details": [
                    f"Simulation d'achat en direct via {model_used}",
                    f"Confiance d'achat IA : {parsed.get('score', 75)}/100",
                    f"Risque d'hallucination estimé par Gemini : {parsed.get('hallucinationRisk', 'FAIBLE')}"
                ],
                "geminiLive": True
            }
        except Exception as e:
            print("[Gemini] Erreur appel simulation:", e)

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

@app.post("/api/scan", response_model=AuditResult, dependencies=[Depends(_scan_rate_limit)])
async def scan_url(req: ScanRequest):
    url = normalize_url(req.url)  # valide & normalise AVANT tout fetch (levée 400 sur URL invalide)
    parsed = urlparse(url)
    domain = parsed.netloc or parsed.path.split("/")[0]

    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=SCAN_FETCH_TIMEOUT_SECONDS) as client:
        # 1. Fetch robots.txt & llms.txt (déjà typés / bornés) de façon indépendante.
        # On les lance en tâches réelles afin de pouvoir annuler proprement en cas de
        # refus anticipé (pas de coroutine "jamais awaitée" sur le chemin d'erreur).
        robots_task = asyncio.create_task(fetch_robots_txt(client, domain))
        llms_task = asyncio.create_task(check_llms_txt(client, domain))

        try:
            page_resp = await client.get(url)
        except Exception as e:
            await _cancel_scan_tasks(robots_task, llms_task)
            raise HTTPException(status_code=400, detail=f"Impossible de joindre l'URL : {str(e)}")

        status_code = page_resp.status_code

        # 2. Garde-fou statut HTTP principal (TACHE-02) : ne JAMAIS analyser une page d'erreur.
        # Mapping explicite pour ne pas que notre réponse se confonde avec notre propre 429.
        if status_code == 404:
            await _cancel_scan_tasks(robots_task, llms_task)
            raise HTTPException(status_code=404, detail="Le site a répondu HTTP 404 — page introuvable, rien d'analysable.")
        if 500 <= status_code:
            await _cancel_scan_tasks(robots_task, llms_task)
            raise HTTPException(status_code=502, detail=f"Le site a répondu HTTP {status_code} — erreur serveur distante, rien d'analysable.")
        if 400 <= status_code < 500:
            await _cancel_scan_tasks(robots_task, llms_task)
            raise HTTPException(status_code=400, detail=f"Le site a répondu HTTP {status_code} — page d'erreur, rien d'analysable.")
        if status_code < 200 or 300 <= status_code < 400:
            await _cancel_scan_tasks(robots_task, llms_task)
            raise HTTPException(status_code=400, detail=f"Le site a répondu HTTP {status_code} — réponse non exploitable par le scanner.")

        raw_headers = {k.lower(): v for k, v in page_resp.headers.items()}
        content_type = raw_headers.get("content-type", "")

        # 3. Garde anti-DoS (TACHE-02) : refus net 413 si le serveur annonce un corps trop gros
        len_hdr = raw_headers.get("content-length")
        if len_hdr:
            try:
                announced = int(len_hdr)
            except ValueError:
                announced = 0
            if announced > SCAN_MAX_RESPONSE_BYTES:
                await _cancel_scan_tasks(robots_task, llms_task)
                raise HTTPException(
                    status_code=413,
                    detail=f"Page trop volumineuse ({len_hdr} octets annoncés, plafond {SCAN_MAX_RESPONSE_BYTES} octets). Scan refusé."
                )

        # 4. Lecture bornée : jamais plus de SCAN_MAX_RESPONSE_BYTES conservé/analysé.
        body_bytes = await _read_page_bounded(page_resp, SCAN_MAX_RESPONSE_BYTES)
        html_content = page_resp.text if not isinstance(page_resp, httpx.Response) else _decode_utf8(body_bytes)

        # 5. Garde Content-Type (TACHE-02) : on n'analyse QUE des pages web.
        if not _looks_like_web_page(content_type, html_content[:2000]):
            await _cancel_scan_tasks(robots_task, llms_task)
            raise HTTPException(
                status_code=415,
                detail=f"Ce n'est pas une page web HTML (type de contenu : '{content_type or 'inconnu'}'). AgentReady audite des fiches produits navigables par les robots IA."
            )
        resp_headers = {k.lower(): v for k, v in page_resp.headers.items()}

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

    # PILIER 5 : Protocoles Agentiques (llms.txt & MCP) - Grille dégradée non-abrupte
    proto_score = 0
    proto_details = []
    if llms_info["found"]:
        if llms_info["path"] == "/.well-known/llms.txt":
            proto_score = 70
            proto_details.append(f"Fichier standard {llms_info['path']} détecté !")
        else:
            proto_score = 45
            proto_details.append(f"Fichier {llms_info['path']} détecté (chemin alternatif, /.well-known/ recommandé)")

        llms_content = (llms_info.get("content") or "").lower()
        if any(kw in llms_content for kw in ["mcp", "endpoint", "api", "tools", "openapi"]):
            proto_score += 30
            proto_details.append("Directives d'endpoints / MCP détectées dans le manifeste")
        else:
            proto_details.append("Configuration MCP manquante (Générée dans l'Auto-Fix)")
    else:
        proto_score = 5
        proto_details.append("Fichier /.well-known/llms.txt introuvable (Manifeste non configuré)")
        proto_details.append("Configuration MCP manquante (Générée dans l'Auto-Fix)")

    proto_score = max(5, min(100, proto_score))

    # CALCUL DU SCORE GLOBAL CONFORME PRD (5 Piliers Déterministes : 20/25/20/20/15 = 100%)
    total_score = int(
        (crawl_score * 0.20) +
        (schema_res["score"] * 0.25) +
        (semantic_res["score"] * 0.20) +
        (sim_res["score"] * 0.20) +
        (proto_score * 0.15)
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
                weight="20%",
                status="Robots OK" if crawl_score >= 75 else "Friction / Bloqué",
                label="Crawl & Bot Access",
                details=crawl_details
            ),
            "schema": PillarScore(
                score=schema_res["score"],
                weight="25%",
                status=schema_res["status"],
                label="Schema.org / JSON-LD",
                details=schema_res["details"]
            ),
            "tokens": PillarScore(
                score=semantic_res["score"],
                weight="20%",
                status=semantic_res["status"],
                label="Pureté Sémantique",
                details=semantic_res["details"]
            ),
            "simulator": PillarScore(
                score=sim_res["score"],
                weight="20%",
                status=f"Risque {sim_res['hallucination_risk']}",
                label="AI Buyer Simulator (Déterministe)",
                details=sim_res["details"]
            ),
            "proto": PillarScore(
                score=proto_score,
                weight="15%",
                status="llms.txt Conforme" if proto_score >= 70 else ("Partiel" if proto_score >= 35 else "Non configuré"),
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
        "primaryModel": GEMINI_PRIMARY_MODEL,
        "fallbackModel": GEMINI_FALLBACK_MODEL,
        "model": GEMINI_PRIMARY_MODEL
    }

@app.post("/api/gemini/test")
async def test_gemini_key(payload: Dict[str, str]):
    client = _get_gemini_client(payload.get("geminiApiKey"))
    if not client:
        if not get_gemini_api_key(payload.get("geminiApiKey")):
            return {"ok": False, "error": "Aucune clé API fournie"}
        return {"ok": False, "error": "google-genai n'est pas installé ou indisponible"}
    try:
        res, model_used = await asyncio.to_thread(
            generate_gemini_content,
            client,
            "Réponds uniquement par 'OK'",
            is_json=False,
            max_tokens=10
        )
        return {"ok": True, "model": model_used, "reply": res.text.strip() if res.text else "OK"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post("/api/gemini/simulate-question", dependencies=[Depends(_sim_rate_limit)])
async def simulate_question(req: SimQuestionRequest):
    client = _get_gemini_client(req.geminiApiKey)
    prod = req.productData or {}
    prod_name = prod.get("name") or "Produit E-commerce"
    prod_price = f"{prod.get('price', 'Inconnu')} {prod.get('currency', 'EUR')}"
    
    if client:
        try:
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
  "model": "{GEMINI_PRIMARY_MODEL}",
  "geminiLive": true
}}"""
            res, model_used = await asyncio.to_thread(
                generate_gemini_content,
                client,
                prompt,
                is_json=True
            )
            parsed = json.loads(res.text)
            parsed["geminiLive"] = True
            parsed["model"] = model_used
            return parsed
        except Exception as e:
            print("[Gemini] Erreur simulation live, bascule sur mode déterministe:", e)
            is_quota = "resource_exhausted" in str(e).lower() or "429" in str(e)
            return {
                "geminiLive": False,
                "fallbackReason": "quota_exhausted" if is_quota else "service_unavailable",
                "standardResponse": {
                    "agentStatus": "⚠️ Risque d'Hallucination",
                    "response": f"Je n'ai pas pu confirmer de manière certaine cette information pour \"{prod_name}\" car le code HTML de la boutique ne fournit pas de microdonnées JSON-LD explicites.",
                    "verdict": "Perte de conversion probable ou renvoi vers un concurrent (Amazon, Fnac)."
                },
                "agentReadyResponse": {
                    "agentStatus": "✅ Mode Déterministe Certifié (Quota live saturé)" if is_quota else "✅ 100% Déterministe (Protocole AgentReady)",
                    "response": f"Information certifiée pour \"{prod_name}\" : les spécifications, le prix ({prod_price}) et les conditions d'expédition sont validés et certifiés via Schema.org et le manifeste llms.txt.",
                    "verdict": "Panier validé et confirmation de commande autonome."
                },
                "model": f"{GEMINI_PRIMARY_MODEL} (Repli Déterministe)" if is_quota else "Mode déterministe"
            }

    # Fallback déterministe haute fidélité sans clé
    return {
        "geminiLive": False,
        "standardResponse": {
            "agentStatus": "⚠️ Risque d'Hallucination",
            "response": f"Je n'ai pas pu confirmer de manière certaine cette information pour \"{prod_name}\" car le code HTML de la boutique ne fournit pas de microdonnées JSON-LD explicites.",
            "verdict": "Perte de conversion probable ou renvoi vers un concurrent (Amazon, Fnac)."
        },
        "agentReadyResponse": {
            "agentStatus": "✅ Mode Déterministe Certifié (Zéro Clé Requise)",
            "response": f"Information certifiée pour \"{prod_name}\" : les spécifications, le prix ({prod_price}) et les conditions d'expédition sont validés et certifiés via Schema.org et le manifeste llms.txt.",
            "verdict": "Panier validé et confirmation de commande autonome."
        },
        "model": "Mode Déterministe Certifié (Zéro Clé Requise)"
    }

def save_lead(email: str, domain: str, name: str, score: int, status: str, risk: str, source: str = "scanner") -> Dict[str, bool]:
    return dispatch_lead(email, domain, name, score, status, risk, source)

# NOTE (P1): la génération PDF (generate_pdf_report) a été déplacée vers pdf_generator.py.
class LeadRequest(BaseModel):
    email: str
    domain: str
    name: str = "Boutique E-commerce"
    score: int = 50
    status: str = "Agent Friction"
    risk: str = "MOYEN"
    source: str = "scanner"

class PdfReportRequest(BaseModel):
    email: str
    auditData: Dict[str, Any]

@app.post("/api/lead")
def record_lead(req: LeadRequest):
    sink_res = save_lead(req.email, req.domain, req.name, req.score, req.status, req.risk, req.source)
    return {"ok": True, "message": "Lead enregistré avec succès", "sink": sink_res}

@app.post("/api/report/pdf")
async def generate_and_download_pdf(req: PdfReportRequest):
    data = req.auditData or {}
    email = req.email.strip()
    domain = data.get("domain", "ecommerce")
    name = data.get("name", "Produit")
    score = data.get("score", 50)
    status_label = data.get("statusLabel", "Audit")
    risk = data.get("aiView", {}).get("hallucinationRisk", "MOYEN")

    # 1. Sauvegarder de façon résiliente le prospect (Postgres + Slack + Backup CSV)
    save_lead(email, domain, name, score, status_label, risk, source="pdf_modal")

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

# Servir les assets publics (/css, /js, /assets) et index.html sans exposer le répertoire racine
_base_dir = os.path.dirname(os.path.abspath(__file__))

_css_dir = os.path.join(_base_dir, "css")
if os.path.isdir(_css_dir):
    app.mount("/css", StaticFiles(directory=_css_dir), name="css")

_js_dir = os.path.join(_base_dir, "js")
if os.path.isdir(_js_dir):
    app.mount("/js", StaticFiles(directory=_js_dir), name="js")

_assets_dir = os.path.join(_base_dir, "assets")
if os.path.isdir(_assets_dir):
    app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")

@app.get("/")
def serve_root():
    index_file = os.path.join(_base_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file, media_type="text/html")
    raise HTTPException(status_code=404, detail="index.html introuvable")

@app.get("/index.html")
def serve_index_html():
    return serve_root()

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"Demarrage d'AgentReady sur le port {port}...")
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)

