# 📊 État des lieux Aiready — MàJ 2026-09-06 (analyse + validation Cline/VPS)

> Source : lecture du repo `main` consolidé (une seule branche, toute la dette fermée), des docs `docs/`, du `server.py`, du front et de la suite de tests (**14/14**). MàJ au 2026-09-06 après consolidation + bouclage prod `aiready-production-a6c0.up.railway.app`.

## 🎯 Le produit (rappel)
SaaS d'audit **"Agentic Readiness"** pour fiches produits e-commerce. Un scan d'URL calcule un **score 0-100 sur 5 piliers pondérés** (Crawl 20 / Schema 25 / Tokens 20 / Simulateur 20 / Protocoles 15), puis un **rapport PDF**, avec **capture de lead** (email) — monnaie principale en phase semi-concierge/high-ticket avant le paywall self-serve P2.

## ✓ Déjà fait (P0 + P1, sprint clôturé, documents dans `docs/issues/`)
- Scoring **5 piliers pondérés** conforme au PRD + `weight` numériques.
- Grille **protocoles dégradée** (plus de basculement binaire brutal).
- Simulateur **100% déterministe au scan** (zéro appel LLM synchrone pénalisant).
- Capture de leads **résiliente** : Postgres/Supabase (transaction) + webhook Slack + backup CSV ; UX "email conservé pour conseil personnalisé" (transparence).
- **CORS durci** (origines via `CORS_ORIGINS`, credentials découplés, méthodes restreintes GET/POST/OPTIONS).
- **Gemini centralisé** : constantes `GEMINI_PRIMARY_MODEL="gemini-3.6-flash"` / `GEMINI_FALLBACK_MODEL="gemini-3.1-flash-lite"`, client factorisé `_get_gemini_client`, **cascade de fallback quota** (zéro 500).
- Herméticité fichiers (pas de StaticFiles racine, `.gitignore` propre, cobayes → `tests/fixtures/`).
- Mini-suite E2E Python (`tests/test_e2e_pipeline.py`, 6 étapes) sous `unittest` + Starlette `TestClient`.
- **Rate-limit anti-abus en mémoire par IP (TACHE-01, validé)** : `/api/scan` (10/60s défaut) + `/api/gemini/simulate-question` (5/60s), fenêtre glissante, purge des IP inactives, parsing `X-Forwarded-For` (dernier élément, anti-spoofing documenté), env `SCAN_*`/`SIM_*`, HTTP **429** + `Retry-After` + JSON. Suite passée à 8 tests.
- **Durcissement du scanner (TACHE-02)** : validation d'URL stricte avant fetch (400 haute précision), rejet net des pages d'erreur (404→404, 5xx→502, autres 4xx→400), rejet `415` des contenus non-HTML, borne anti-DoS `413`/troncature (`SCAN_MAX_RESPONSE_BYTES`), timeout configurable clampé (`SCAN_FETCH_TIMEOUT_SECONDS`), lecture bornée en streaming. Suite → 14 tests.
- **UX erreurs backend explicites (TACHE-03)** : bandeau `#scan-error-box` affichant les 4xx/5xx réels (plus de faux fallback friction), bouton "Réessayer" + lien conseiller, transparence du repli démo en cas d'échec réseau.
- **Consolidation** : l'ensemble du travail (TACHE-01/02/03) est livré sur une branche **`main` unique** et **vérifié en prod** sur `aiready-production-a6c0.up.railway.app` (A3) : behaviours TACHE-01/02/03 observés en ligne.

## ⚠️ État de la base de code
- **Stack réelle embarquée :** serveur **FastAPI `server.py` unifié** (API + HTML/CSS/JS statique servi en dur, ~1290 + ~210 lignes back, front vanille `index.html` (1002) + `js/*`). Pas de Next.js (c'était la cible, non livrée). Runtime Python **3.11.9**. Déploiement Railway/Render via `Procfile`/`railway.json`.
- **Fonctions API exposées :** `/api/scan` (POST, scan+score), `/api/gemini/status`, `/api/gemini/test`, `/api/gemini/simulate-question`, `/api/lead`, `/api/report/pdf`, `/api/health`, `/` + statiques.
- Front : 5 mini-cartes de score + éventuel indicateur (déterministe/live/quota). Cohérence avec 20/25/20/20/15 (testé).

## 🕳️ Ce qui manque / risques ouverts (à décider avec l'utilisateur)
> MàJ Cline/VPS (après TACHE-01/02/03 + consolidation) : la dette technique P1 identifiée en début de cycle est **fermée**. Risques/maxes restants :
1. **Rate-limit mono-processus → multi-réplicas** : observé en prod, le blocage 429 est seulement *intermittent* quand Railway fait tourner plusieurs instances (le compteur n'est pas partagé). Durcir = **Redis distribué** (cadré P2 ; le front supporte déjà le 429 non-fatal).
2. **Réglages de seuils produit** : 5 requêtes/60s sur `/simulate-question` peut être ressenti comme serré pour un usage légitime de démo ; le score est auto-ajustable via env (`SIM_RATE_LIMIT`).
3. **Dépendances externes / tunnel réel d'un vrai site tiers** : le moteur scan « 0 Playwright/Cheerio » est fonctionnel en dur (htm + bs4) ; la validation d'un audit 100 % déterministe sur un site réel (WAF, CSR lourd) reste à prouver par un ou deux scans « client-ready » de démo (liste à fournir en démo).
4. **Bloc P2** (non commencé) : Auth + espace client, Paywall Stripe 49€/199€, dashboard de monitoring récurrent, scan en masse + PDF white-label, boutique onboarding.

## 🔎 Constats techniques à connaître avant d'implémenter
- Le front est du **JS vanille** + HTML monolithique ; pas de framework → les changements UI se font en édition directe HTML/JS + CSS.
- Les **constantes Gemini résident dans `server.py`** (module importé par les tests) ; les pondérations aussi → toute modif de calcul doit rester alignée avec le test E2E `test_01` et les critères `ISSUE-01`.
- Pas de CI visible dans le repo (pas de `.github/workflows`) → les vérifications se font en local via `python -m pytest tests/test_e2e_pipeline.py` (unittest, donc lancer avec `python -m unittest` ou via discovery).
- Les tests s'exécutent sans clé Gemini ni DB réelle (mock) → exécutables en local sans config.

## Verdict Cline/VPS (après TACHE-01/02/03 + bouclage prod A3, 2026-09-06)
Le produit est **solide, cohérent et "vérité 0 variance en direct"** désormais validé **en production** (`aiready-production-a6c0.up.railway.app`) depuis une branche `main` unique consolidée :
- durcissement anti-abus scan (TACHE-01/02) et UX erreurs (TACHE-03) **livrés et observés en ligne** ;
- suite **14/14** verte ; aucune régression ;
- prochaine monétisation (Famille B) ou **migration Redis du rate-limit (P2)** selon l'arbitrage utilisateur dans `02-ROADMAP-EXECUTION.md`.
