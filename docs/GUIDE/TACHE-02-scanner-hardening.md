# 🛡️ TACHE-02 — Verrouillage du scanner `/api/scan` (gardes réseau & bornes de ressources)

> **Statut :** proposée par Cline/VPS (source `docs/GUIDE/02-ROADMAP-EXECUTION.md` lot **A2**).
> **Portée :** UNE seule livraison cohérente de durcissement de `/api/scan` côté **backend** — ne coder aucune réécriture d'UX, aucun refactor, aucune modif réseau des autres endpoints. N'introduire **aucune** dépendance externe.
> **Suite logique :** repose sur la `TACHE-01` (rate-limit) déjà livrée sur `wip/tache-01-ratelimit`.

---

## 🎯 Objectif
Empêcher qu'un `/api/scan` consomme des ressources réseau/CPU/mémoire disproportionnées ou produise un **résultat faux** sur des entrées ou réponses que le moteur ne sait pas traiter. Aujourd'hui (verdict Cline/VPS) :
- Timeout de fetch **codé en dur** (`timeout=12.0` dans `httpx.AsyncClient`) → non configurable.
- `normalize_url` très laxiste → aucune validation **avant** un fetch réseau inutile (schéma invalide, URL énorme, espaces…).
- La réponse HTTP principale est analysée **quel que soit** `status_code` (une page d'erreur 404/401/429/5xx est "scannée" comme si c'était un produit).
- Le **`Content-Type`** n'est jamais inspecté → un PDF/image/API JSON est parsé en HTML (résultat absurde + gaspillage).
- Un document HTML très volumineux est **chargé en entier** en mémoire puis parsé → risque d'épuisement mémoire/CPU.

## ▸ Contexte technique (vérifié par Cline/VPS)
- Tout est dans `scan_url(req: ScanRequest)` (actuellement ~l.743 dans la branche ratelimit, ~l.598 dans `guide`). `httpx` est déjà importé ; l'`AsyncClient` global porte `headers=HEADERS, follow_redirects=True, timeout=12.0`.
- `fetch_robots_txt` (timeout 5.0) et `check_llms_txt` (timeout 4.0) fixent déjà leurs propres timeouts **inline**, à NE PAS toucher (ils partent en parallèle de la page principale).
- `normalize_url(raw_url) -> str` (en tête de fichier, ~l.124) préfixe `https://` sur tout ce qui n'est pas `http(s)://`. Aucun garde-fou.
- `ScanRequest.url: str` (pydantic). `AuditResult` inchangé.
- Le front appelle `POST /api/scan` ; tout échec HTTP `!response.ok` est déjà absorbé **sans crash** par `js/scanner-simulator.js` (fallback heuristique non-fatale). Donc de nouveaux codes 4xx restent non-fatals. On NE change RIEN au front dans cette tâche.
- Style env : `os.getenv(...)` (cf. config CORS / limiters TACHE-01). Le projet tourne **uvicorn monoprocessus** ; les limites en mémoire par module sont OK.

---

## 🎯 Spécification (proposition Cline/VPS — seuils ajustables)

### 1. Timeout réseau CONFIGURABLE par env
Remplacer le `12.0` codé en dur par une valeur lue (défauts documentés), appliquée à l'`AsyncClient` principal du scan :
- `SCAN_FETCH_TIMEOUT_SECONDS` — défaut `12` (int >0, borne haute de sécurité imposée **60** si quelqu'un passe un très grand nombre via env → clamp `max(1, min(60, value))`).

### 2. Validation d'entrée STRICTE avant tout fetch (anti-abus réseau)
Améliorer `normalize_url`/l'entrée pour valider **dès la requête**, sans fetch :
- N'accepter que les schémas `http://` et `https://` (case-insensitive). Sinon **400**.
- Rejeter toute URL contenant espaces/tabs/newline ou de longueur > 2048 caractères → **400**.
- Exiger un nom d'hôte (netloc) non vide ; si `https://` ajouté, toujours convertir. Renvoyer l'URL normalisée.
- Toutes ces erreurs : `HTTPException(status_code=400, detail="…")` avec un `detail` **court, compréhensible en français**. Front : aucune de ces réponses ne doit déclencher de 500.

Messages type (wording ajustable, rester explicite) :
- `"URL non valide : seuls les liens http:// et https:// sont acceptés."`
- `"URL trop longue (max 2048 caractères)."`
- `"URL invalide : hôte manquant."`

> ⚠️ Ces validations doivent avoir lieu **avant** `httpx.AsyncClient(...)`. Une URL absurde doit être rejetée en quelques µs, sans requête réseau sortante.

### 3. Statut HTTP réel : refuser NET une réponse non réussie
Après le premier `client.get(url)` de la page principale :
- Si `status_code >= 400` → **400** (ou **404** si la réponse est un 404 net) avec `detail` explicite du genre `"Le site a répondu HTTP {code} — page d'erreur, rien d'analysable."` On **n'analyse PAS** le corps d'une page d'erreur.
- Cas `status_code` 2xx (ou 3xx déjà suivie par httpx en `follow_redirects`) → continuer normalement.
- L'analyse du score doit rester **inchangée** quand la page est saine.

### 4. Content-Type : refuser ce qui n'est pas une page web HTML
Inspecter l'en-tête `content-type` de la réponse principale :
- Accepté : contient `text/html`, `application/xhtml+xml`, ou `text/plain` **si** le corps contient clairement un balisage `<!` / `<html` (palliatif pour sites qui servent `text/plain`). En l'absence de toute balise, refuser.
- Refus sinon avec **415** et `detail` : `"Ce n'est pas une page web HTML (type de contenu : {type}. AgentReady audite des fiches produits navigables par les robots IA.")`
- `robots.txt` / `llms.txt` ne passent pas par ce contrôle (sous-fetch séparés).


### 5. Borne de taille de document téléchargé (anti-DoS mémoire/CPU)
- Faire en sorte qu'on **ne charge ni n'analyse jamais plus de `SCAN_MAX_RESPONSE_BYTES`** octets du HTML principal.
- Défaut proposé : `2_000_000` (2 Mo). Configurable `SCAN_MAX_RESPONSE_BYTES` (env, clamp ≥ 100 Ko).
- Deux comportements au choix, documentez votre choix en commentaire :
  - (a) __Refuse 413__ si `Content-Length` annoncé dépasse la borne ; sinon requête normale puis on parse le corps (fiable quand `Content-Length` est présent) ;
  - (b) __Tronque__ : on lit au maximum la borne (ex. ré-émission en stream `client.stream` sans lire au-delà de la borne), puis on analyse la page tronquée. C'est le plus robuste aux sites qui ne fournissent pas `Content-Length`.
- Exigence **non négociable** : aucun chemin ne doit stocker plus que la borne dans `html_content` passé à `BeautifulSoup`. Ne pas modifier `httpx.Limits` global (cela affecterait robots/llms).

## 📄 Fichiers concernés
- `server.py` (majoritairement) : validation d'entrée, timeouts/env, contrôles status-code & content-type & taille dans `scan_url`, constantes de bornes en tête de fichier avec les autres réglages `os.getenv`.
- Optionnel mais encouragé : éventuel petit helper dédié (`_is_web_page_content`, `_clamp_int_env`, etc.) si ça reste lisible et testable.
- `tests/test_e2e_pipeline.py` (ajout en fin, mêmes conventions unittest) : nouveaux tests ci-dessous.

## ⚙️ Règles d'exécution (contraintes)
1. **Aucune dépendance nouvelle** (`requirements.txt` inchangé). Tout est faisable avec `httpx` + stdlib présents.
2. **Ne pas modifier** les timeouts internes dédiés robots/llms ni leur logique.
3. **Champ d'application strict** : uniquement le bloc page principale de `scan_url`. Ne pas toucher `/api/gemini/*`, `/api/lead`, PDF, statiques, ni UI.
4. Respecter la config par env via `os.getenv` + clamp, comme déjà pratiqué.
5. Maintenir une **régression totale** : suite existante verte (les 8 tests, dont vos 2 rate-limit de TACHE-01).
6. Les **nouvelles erreurs restent non-fatales** (JSON `detail` familier, jamais 500). Le front continue d'afficher son fallback sans crash.


## 🔍 Points d'attention (relire avant de coder)
- `httpx.Response.text` est décodé entièrement → pour la borne taille (option b), utiliser `client.stream` puis lecture bornée de `aiter_bytes`, ou au minimum une garde sur `Content-Length` avant la lecture `.text`. Ne pas lire 50 Mo pour ensuite tronquer.
- Les URLs de test existantes utilisent `https://boutique-test.fr` sur le domaine `boutique-test.fr` → gardez la normalisation compatible (préfixe `https://` si protocole absent) pour ne pas casser `test_01` / `test_07`.
- Après une `HTTPException` FastAPI, le front répond toujours via son fallback → vérifier qu'aucun nouveau scénario ne lève hors try/catch ni ne retourne 500.
- Un status final 3xx ne devrait pas être observable après `.get()` avec `follow_redirects=True`, mais couvrez le cas (refus net) pour la robustesse.

## ✔️ Definition of Done (tous doivent passer)
- [ ] URL schéma non `http(s)`, ou espaces/saut de ligne, ou > 2048 chars, ou sans hôte → **400 en quelques µs (aucun fetch réseau)**, `detail` clair.
- [ ] Réponse principale `status_code >= 400` → refus net (400/404) **sans** analyse du corps d'erreur.
- [ ] `content-type` principal non-HTML net → **415** ; HTML → scan normal.
- [ ] Document HTML > borne → jamais chargé/analysé au-delà de la borne (413 ou troncature documentée), sans casser robots/llms.
- [ ] Timeout configurable par env `SCAN_FETCH_TIMEOUT_SECONDS` (clamp 1..60) effectivement utilisé par l'`AsyncClient` principal.
- [ ] Bornes/timeouts documentés en commentaire (en tête de `server.py` où sont les autres réglages `os.getenv`), ajout au `.env.example` recommandé.
- [ ] Nouvelles fonctions de test (au moins **5** scénarios : validation entrée, refus 404/429, refus non-HTML 415, borne taille, timeout configurable) ajoutées et **suite complète verte**.
- [ ] Aucune régression : les 8 tests antérieurs restent verts.
- [ ] Commits propres, messages clairs, sur branche `wip/`, **SANS toucher à `docs/GUIDE/`**.

## ▶️ Comment lancer et vérifier (obligatoire avant de déclarer terminé)
```bash
cd <racine-du-repo>
python3 -m unittest discover -s tests -p "test_*.py" -v
```
Toute la suite doit être verte (`OK`), sans clé Gemini ni DB réelle (montage par mock).

## 🖇️ Notes d'arbitrage ouvertes pour l'utilisateur
- Le front affiche aujourd'hui un **fallback heuristique** sur toute erreur backend (`js/scanner-simulator.js`) : une URL réellement non-HTML ou bloquée sera présentée comme un résultat friction-type, pas comme une erreur explicite. Correct en démo, potentiellement trompeur en production. Cline/VPS propose de traiter l'affichage d'erreur explicite (HTTP 4xx → message clair au lieu du fallback) dans une **TACHE-03 UX** séparée — pas dans celle-ci. À arbitrer.

