# Audit AgentReady (AIReady Commerce) — 2026-09-09

## Problème n°1 : le marché "Blue Ocean" annoncé dans `docs/MARKET_ANALYSIS.md:46-66` n'existe plus

Recherche web (sept. 2026) : au moins **9 scanners "AI readiness" gratuits et actifs** couvrent le même besoin (score 0-100 + génération `llms.txt`) : IndexedAI, isagentready.com, AI Web Readiness, AgentReady.md (conflit de nom direct), agent-ready.dev, Search Engine Land AI Agent Readiness Checker, AdNabu, LLM Pulse, Ayzeo, WebTrek. Surtout : **Shopify a lancé son propre scanner natif gratuit** (`shopify.com/agentic-readiness`, 31 checks / 5 catégories, sans login) — il touche directement l'ICP n°1 du projet (marchands Shopify/WooCommerce, `docs/MARKET_ANALYSIS.md:78-81`). Le document stratégique interne date visiblement d'avant cette vague et présente comme différenciateurs des éléments déjà banalisés.

## Problème n°2 : le différenciateur revendiqué #2 est trompeur — le score principal ne fait aucun appel LLM

`docs/MARKET_ANALYSIS.md:70` promet : *"envoie de vraies requêtes d'achat à des LLMs"*. Or `server.py:1656` : *"PILIER 4 : AI Buyer Simulator (100% Déterministe en V1 - Zéro appel LLM au scan)"* — ce pilier du score gratuit est un moteur de règles, pas un LLM. Le seul vrai appel Gemini vit dans un endpoint séparé (`/api/gemini/simulate-question`, `server.py:1951`), limité à 5 req/min (`server.py:240-241`), sans clé par défaut (`.env.example:2`), et qui **retombe silencieusement en mode déterministe** dès qu'il manque une clé ou un quota (`server.py:1990-2025`) — reproduit pendant cet audit (log : `RESOURCE_EXHAUSTED: 429 quota limit reached` → bascule auto). La promesse marketing n'est donc pas tenue par défaut.

## Problème n°3 : authentification du dashboard basée sur la seule connaissance d'un email

`server.py:2400-2412` (`/api/dashboard/login`) : aucune vérification de mot de passe ni de lien magique. La fonction vérifie seulement qu'un abonnement Stripe actif existe pour l'email fourni (`_has_active_subscription`, `server.py:2374-2397`) puis délivre un token HMAC signé. Un email pro de client payant est souvent public (site, LinkedIn, facture partagée) : quiconque le connaît peut se connecter et lire l'historique de scans associé. Pas de données bancaires exposées, mais c'est une vraie faille d'autorisation, non couverte par les tests (`tests/test_e2e_pipeline.py` ne teste aucun endpoint `/api/dashboard/*`).

---

## Phase 1 — Audit technique détaillé

### Architecture

| Aspect | Constat | Preuve |
|---|---|---|
| Structure | Monolithe FastAPI unique, pas de séparation domaine/infra | `server.py` = 2658 lignes, un seul fichier pour scan, PDF, dashboard, email, Stripe |
| Découplage récent | Extraction partielle de `pdf_generator.py`, `lead_sink.py`, `email_sequence.py` | `server.py:46-48` (imports) |
| Persistance | PostgreSQL avec repli CSV/JSON local en cas d'échec | `server.py:2202-2351` |
| Concurrence | Rate-limiter en mémoire, **mono-process** | `server.py:168-170` : "NOTE: ce mécanisme est mono-processus... En multi-worker, il faudra migrer vers Redis (prévu P2)" — donc non scalable horizontalement en l'état |
| Rendu JS | Pas de rendu JS (Playwright annoncé en roadmap, absent du code) | `requirements.txt` ne liste pas Playwright ; README annonce Playwright comme "cible P2" (`README.md:51-52`) alors que le PRD le présente comme composant du MVP (`docs/PRD.md:86`) — incohérence entre doc produit et doc technique |

Point de rupture au scaling identifié : le rate-limiter et le cache de scans sont en mémoire process — un redéploiement Railway ou un scale à 2 workers casse silencieusement les quotas et la cohérence de session dashboard (token signé HMAC stateless, ok, mais quotas non partagés).

### Qualité & tests

- 43 tests unitaires (`unittest`), tous verts en local (`python -m unittest discover` → `OK`, 22s).
- Bonne couverture sur le cœur métier : SSRF (`test_15`, `test_20`, `test_22`), rate-limit (`test_07/08/16/23/32`), robots.txt (`test_17/25/26/30`), extraction d'image (`tests/test_image_extraction.py`).
- **Zéro test** sur `/api/dashboard/login`, `/api/dashboard/save`, `/api/dashboard/scans`, `/api/process-email-sequence`, `/api/process-payment-welcome` — soit ~500 lignes de `server.py` (2050-2460) non couvertes, incluant la faille d'autorisation ci-dessus.
- CI GitHub Actions fonctionnelle (`.github/workflows/ci.yml`), un seul job Python 3.11, pas de lint/type-check (pas de `mypy`/`ruff` dans le pipeline).

### Sécurité

- Points forts vérifiés : garde SSRF structurelle + DNS (`server.py:420-507`), SQL paramétré (`%s`, `server.py:2235-2345`), headers de sécurité (CSP/HSTS/X-Frame-Options, `server.py:80-96`), aucun secret en dur (grep négatif sur tout le repo), suppression récente d'un défaut HMAC en dur (commit `876ae9c`).
- Faille identifiée : authentification dashboard par email seul (voir Problème n°3).
- Dépendances : `pip-audit` signale `cryptography==41.0.7` vulnérable (dont `GHSA-h4gh-qq45-vh27`), tirée transitivement par `google-genai` → `google-auth` (dépendance directe, `requirements.txt:8`). Correctif : forcer `cryptography>=43`. Les autres paquets signalés (`httplib2`, `pyjwt`, `pip`, `setuptools`) appartiennent à l'image système, pas au projet.
- `requirements.txt` n'épingle aucune version exacte (`>=` partout) : build non reproductible à chaque déploiement Railway.

### Coût d'exploitation

- Stack Railway/Render + Postgres managé + Resend + Gemini à la demande : coût variable faible tant que le volume est bas.
- Coût caché : appel Stripe API synchrone à **chaque login dashboard** (`server.py:2374-2397`, 2 requêtes HTTP externes) — latence et dépendance tierce pour une simple authentification.
- Le mode déterministe par défaut limite le coût Gemini réel (bon pour la marge, mauvais pour l'honnêteté produit — cf. Problème n°2).

---

## Phase 2 — Analyse marché (sourcée)

| Concurrent | Prix (2026) | Positionnement | Ce qu'il fait / que le projet ne fait pas |
|---|---|---|---|
| **Shopify Agentic Commerce Audit** | Gratuit | Natif Shopify, 31 checks / 5 catégories | Distribution massive, 0 friction ; ne couvre pas WooCommerce/Magento ([Craftshift](https://craftshift.com/shopify-agentic-readiness-scanner-guide/)) |
| **IndexedAI** | Gratuit | Score 0-100 + `llms.txt`/`llms-full.txt` | Quasi identique au scan gratuit AgentReady ([scriptbyai.com](https://www.scriptbyai.com/indexedai-agent-readiness-score/)) |
| **Profound** | 99-399 $/m, entreprise 2-5k$/m | Tracking de citations de marque ChatGPT/Perplexity, valorisation $1 Md (série C $96M, fév. 2026) | Pas d'audit technique de fiche produit ni d'auto-fix ; autre catégorie ([Rankability](https://www.rankability.com/blog/profound-ai-review/)) |
| **Peec AI** | 95-495 $/m | Reporting de visibilité IA, 3-6 moteurs | Monitoring pur, pas de correction ([get-ryze.ai](https://www.get-ryze.ai/blog/peec-ai-review-pricing-2026)) |
| **Otterly.ai** | 29-489 $/m | Monitoring multi-moteurs + MCP/API en plans hauts | Idem Peec ; pas de monitoring récurrent chez AgentReady ([Otterly](https://otterly.ai/pricing)) |

**Taille de marché (sourcée, chiffres très variables selon méthodologie) :** "commerce agentique" estimé entre 7,7 Md$ et 60,4 Md$ en 2026, vers 3-5 000 Md$ d'ici 2030 selon McKinsey ; ChatGPT traite 50M requêtes shopping/jour, 900M utilisateurs hebdo, fév. 2026 (source: [Grand View Research](https://www.grandviewresearch.com/industry-analysis/agentic-commerce-market-report), [Paz.ai](https://www.paz.ai/agentic-commerce-statistics)). La demande de fond est réelle — ce n'est pas le problème.

**Barrières à l'entrée : quasi nulles.** Un score pondéré sur `robots.txt` + JSON-LD + comptage de tokens + template `llms.txt` est reproductible en quelques jours par un dev seul avec un LLM de code — preuve : 8+ clones existent déjà en 2026, plusieurs au pitch identique ("score 0-100", "5 axes", "llms.txt en 1 clic"). Hors garde SSRF (hygiène standard, pas un avantage produit), rien dans le code n'est une barrière technique défendable.

---

## Phase 3 — Verdict

### Les 3 problèmes qui tuent le projet, par gravité

1. **Pas de fossé défendable** : le score + `llms.txt` + JSON-LD est commoditisé, gratuit chez Shopify pour l'ICP principal, et cloné par une dizaine d'outils. Sans fossé, le prix (49-199€/m) est arbitrable à zéro par la concurrence gratuite.
2. **Promesse produit non tenue par défaut** : le pilier "IA" phare (AI Buyer Simulator) est scripté, pas du LLM, sur le parcours gratuit qui sert de preuve de valeur avant paiement — risque de déception client et de retours négatifs si découvert (et c'est visible en lisant le code source, donc découvrable par un concurrent ou un client technique).
3. **Solo founder, produit vieux de 3 jours, zéro signal de traction** (46 commits entre le 6 et le 9/09/2026, `git log`) : aucune preuve de client payant, de MRR, ou de rétention. Les OKR du PRD (10 000 scans/60j, 25k$ MRR/4 mois, `docs/PRD.md:18-20`) sont des objectifs, pas des résultats mesurés — non vérifiable en l'état.

### Différenciateur réel ?

Aucun différenciateur défendable identifié. Le multi-CMS et l'angle agence/marque-blanche sont réels mais faibles : Shopify couvre déjà la plus grosse part du D2C, et le "GEO monitoring" (Profound/Peec/Otterly) sert un autre besoin (visibilité de marque récurrente), plus monétisable que l'audit ponctuel. Franchement : c'est un produit de commodité sur un marché que l'acteur dominant de la niche (Shopify) vient d'aspirer gratuitement.

### Go / No-go / Pivot

**Pivot.** Ne pas vendre l'audit ponctuel en concurrence frontale avec l'outil gratuit de Shopify. Deux pistes, sans jeter le code existant :
- Monitoring récurrent (comme Profound/Peec/Otterly), prix d'entrée PME (29-49€/m) — demande payante déjà prouvée, mais marché mature à rattraper.
- Vertical B2B/catalogue complexe (ICP 3, `MARKET_ANALYSIS.md:86-88`) délaissé par Shopify et les clones, avec un vrai moteur d'enrichissement, pas qu'un score.
Sans changement de positionnement, "No-go" commercial est la conclusion honnête sur le pricing actuel.

### 3 prochaines actions, par ordre de priorité

1. **Corriger la faille d'autorisation dashboard** (`server.py:2400-2412`) avant tout push marketing — lien de connexion à usage unique par email plutôt qu'un login par email seul.
2. **Aligner le discours sur le code** : activer réellement le LLM sur le pilier 4 du scan gratuit, ou retirer la promesse "vraies requêtes d'achat aux LLMs" — le risque réputationnel dépasse le gain marketing.
3. **Trancher le pivot avant tout développement supplémentaire** : interroger 10 prospects de l'ICP visé sur leur volonté de payer 49-199€/m *après leur avoir montré le scanner gratuit de Shopify* — si négatif, arrêter l'axe "scanner ponctuel" immédiatement.
