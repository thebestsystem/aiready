# 🗺️ FEUILLE DE ROUTE MVP « COMMERCIALISABLE » — Aiready / AgentReady

> Document de pilotage cofondateur. Statut cible : correctifs P0/P1 avant la vente manuelle,
> P2 après validation du premier flux semi-concierge.

---

## Stratégie de lancement (rappel, actée)
**Semi-concierge / High-ticket d'abord** (J0–J60) : le scanner gratuit + le rapport PDF servent de *trojan horse* pour capturer des leads. On vend à la main des **packs « Mise en conformité AgentReady » 500 € – 1 500 €** (audit complet + JSON-LD corrigé + `llms.txt` + déploiement assisté).  
**P2 self-serve** (J60–J90) : espace client, monitoring récurrent, abonnement Stripe 49 €/199 €.

**Conséquence immédiate :** pas de code paywall Stripe à J1. En revanche, la capture de leads DOIT être irréprochable (c'est notre seule monnaie), et le produit ne doit pas nous mettre en porte-à-faux face à un prospect exigeant.

---

## P0 — Bloquants à corriger AVANT toute vente / démo payante

| # | Sujet | Issue | Impact si non fait |
|---|-------|-------|--------------------|
| P0-1 | Score global sur **5 piliers** pondérés conformes au PRD (25/30/20/25 + bonus) + `weight` numériques + simulateur/protocoles intégrés à la note | #1 | Vendre 5 piliers, en calculer 3 → perte de crédibilité au premier client pointilleux |
| P0-2 | Dépollution racine + `.gitignore` (scripts cobayes, `leads.csv`, env) | #4 | Repo non "client-ready", risque de fuite (emails, clés) si commit |
| P0-3 | Capture de leads **résiliente** : Postgres managé (transaction) + webhook Slack temps réel + backup CSV local | #5 | Perdre la monnaie (emails) au premier redeploy |

## P1 — Fiabilité / production (avant mise en échelle)

| # | Sujet | Issue | Note |
|---|-------|-------|------|
| P1-1 | Harmoniser les références **modèles Gemini** via constantes (`GEMINI_PRIMARY_MODEL="gemini-3.6-flash"`, `GEMINI_FALLBACK_MODEL="gemini-3.1-flash-lite"`), client SDK factorisé, gestion quota/fallback | #2 | Chaînes en dur incohérentes entre backend et réponse `model` affichée |
| P1-2 | Config **CORS** propre (origines via env, credentials séparés) | #3 | Conformité navigateur + limiter l'abus du scanner |
| P1-3 | **Limitation d'usage** légère (rate-limit basique sur `/api/scan` par IP + refroidissement) | — *à ouvrir* | Anti-abus minimal avant tout traffic réel |
| P1-4 | **Validation & tests** : un mini-suites `tests/` (déplacés de la racine) pour piloter le score d'exemple | — *dans #4* | Prémunir une régression sur le scoring |

## P1b — Fiabilité produit (détaillée, avant de promettre au client le score "0 variance, 0 hallucination")
| # | Sujet | Pourquoi |
|---|-------|----------|
| P1b-1 | Rendre le pilier **Protocoles** non abrupt (grille dégradée plutôt que 0↔70) | Éviter qu'un score "global" verse à cause d'un seul fichier absent ; score = somme dégradée |
| P1b-2 | Vérifier la **cohérence UX** : paquet PDF dispo sans gating, mais message clair "email conservé pour conseil personnalisé" (transparence RGPD) | Conformité + confiance, pas de surprise sur l'email |
| P1b-3 | Garder le scan **synchrone sans appel LLM** pénalisant (simulateur déterministe seulement au score) | Performance page conservée |

## P2 — Suite (J60–J90) quand le manuel a validé la valeur
1. **Auth + Espace Client** (invitation, historiques d'audits, re-scans). 
2. **Paywall Stripe** (Free / Pro 49 € / Agency 199 € selon grille PRD) : quotas par plan, webhooks Stripe.
3. **Dashboard de monitoring récurrent** (re-scan périodique, alerte de régression de score).
4. **Scan en masse** (batch URLs + export CSV/Excel) + **PDF white-label** pour agences.
5. **Boutique** : onboarding de déploiement du fix (injection JSON-LD + llms.txt) en produit tour.

---

## Cadence d'exécution (actée) — pour l'équipe Antigravity

### Sprint Immédiat — P0 (Hygiène & Crédibilité)
1. **#4 Dépollution du repo** : déplacement de `welcomeoffice` + scripts de test → `tests/fixtures/`, `.gitignore` au propre (CSV locaux, dumps, caches, env). *Terrain net avant tout autre commit.*
2. **#1 Alignement strict du Score 5 Piliers** : pondération PRD dans `server.py` (25 / 30 / 20 / 25 + bonus), `weight` numériques, simulateur/protocoles dans la note.
3. **#5 Résilience des Leads** : persistance **Postgres** (transaction) + webhook **Slack/Discord** + backup CSV local ; fix UX "lead vs succès PDF" côté front.

### Sprint Stabilisation — P1
4. **#3 Sécurisation CORS** : corriger le combo `allow_origins` / `allow_credentials` (origines via env).
5. **#2 Centralisation Gemini** : constantes `GEMINI_PRIMARY_MODEL` / `GEMINI_FALLBACK_MODEL`, client SDK factorisé, gestion quota/fallback.
6. Fiabiliser avec un mini-jeu de **tests d'exemple** (JS/Python) validant les pondérations + ci-dessus.
