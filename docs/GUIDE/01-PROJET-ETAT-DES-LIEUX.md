# 📊 État des lieux Aiready — au 2026-09-06 (analyse Cline/VPS)

> Source : lecture du repo `main` (`9 commits`), des docs `docs/`, du `server.py`, du front et du test E2E.

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

## ⚠️ État de la base de code
- **Stack réelle embarquée :** serveur **FastAPI `server.py` unifié** (API + HTML/CSS/JS statique servi en dur, ~1290 + ~210 lignes back, front vanille `index.html` (1002) + `js/*`). Pas de Next.js (c'était la cible, non livrée). Runtime Python **3.11.9**. Déploiement Railway/Render via `Procfile`/`railway.json`.
- **Fonctions API exposées :** `/api/scan` (POST, scan+score), `/api/gemini/status`, `/api/gemini/test`, `/api/gemini/simulate-question`, `/api/lead`, `/api/report/pdf`, `/api/health`, `/` + statiques.
- Front : 5 mini-cartes de score + éventuel indicateur (déterministe/live/quota). Cohérence avec 20/25/20/20/15 (testé).

## 🕳️ Ce qui manque (source principale : `docs/ROADMAP-MVP.md` + le rapport)
Trois sujets de P1 restent explicitement **non traités** , puis le bloc P2 :
1. **P1-3 — Rate-limit anti-abus** sur `/api/scan` (par IP + refroidissement). Marqué "à ouvrir". **Rien dans le code** (aucun throttle/cooldown trouvé). → Première bonne cible d'implémentation robuste et isolée.
2. **Validation matérielle** du tunnel complet hors simulateur (le test E2E existe, mais tourne-t-il réellement ? à vérifier).
3. **Dépendances externes** : Scan en direct réellement déployable ? (httpx, beautifulsoup4, postgres, etc. présents dans requirements ; **pas de Playwright/Cheerio** alors que la cible le prévoyait).

Le **bloc P2** (non commencé) : Auth + espace client, Paywall Stripe 49€/199€, dashboard de monitoring récurrent, scan en masse + PDF white-label, boutique onboarding.

## 🔎 Constats techniques à connaître avant d'implémenter
- Le front est du **JS vanille** + HTML monolithique ; pas de framework → les changements UI se font en édition directe HTML/JS + CSS.
- Les **constantes Gemini résident dans `server.py`** (module importé par les tests) ; les pondérations aussi → toute modif de calcul doit rester alignée avec le test E2E `test_01` et les critères `ISSUE-01`.
- Pas de CI visible dans le repo (pas de `.github/workflows`) → les vérifications se font en local via `python -m pytest tests/test_e2e_pipeline.py` (unittest, donc lancer avec `python -m unittest` ou via discovery).
- Les tests s'exécutent sans clé Gemini ni DB réelle (mock) → exécutables en local sans config.

## Verdict Cline/VPS
Le produit est **solide et cohérent pour l'étape P0/P1**. Le travail le plus utile à court terme = **fermer le dernier P1 ouvert (rate-limit)** puis **préparer le tunnel P2** (auth/quotas) ; mais tout dépend de la stratégie commerciale actée (semi-concierge d'abord). Nous laissons l'utilisateur trancher la priorité dans `02-ROADMAP-EXECUTION.md`.
