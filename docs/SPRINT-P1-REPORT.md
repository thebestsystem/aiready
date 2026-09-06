# 🏁 Rapport de Fin de Sprint P1 — Stabilisation produit

> **Statut :** Sprint clôturé & poussé sur `origin/main`.  
> **Objectif :** Durcir la production (sécurité, robustesse IA, résilience) du MVP Aiready/AgentReady après le lot P0 (hygiène + scoring 5 piliers).

---

## 📦 Livrables du Sprint P1

| Commit | Ticket | Contenu | Statut |
|--------|--------|---------|:---:|
| `0000ab4` | **#3 CORS** | Origines strictes via `CORS_ORIGINS`, découplage `allow_credentials`, méthodes restreintes `GET/POST/OPTIONS` | ✅ Poussé |
| `357a6ce` | **#2 Gemini** | Constantes `GEMINI_PRIMARY_MODEL`/`FALLBACK`, client factorisé `_get_gemini_client`, cascade de fallback quotas | ✅ Poussé |

---

## ✅ Ticket #3 — Sécurisation CORS

### Comportement cible & implémenté
- **Mode par défaut (front same-origin / API publique) :** `allow_origins=["*"]`, `allow_credentials=False`  
  → conforme navigateur (pas de cookie), zéro conflit AWS/W3C.
- **Mode whitelist (`CORS_ORIGINS`) :** origines déclarées seules autorisées, `allow_credentials=True` activé.
- **Méthodes restreintes :** `GET`, `POST`, `OPTIONS`.

### Variables d'environnement
| Variable | Type | Rôle |
|----------|------|------|
| `CORS_ORIGINS` | CSV | Liste d'origines autorisées (ex. `https://agentready.io,http://localhost:3000`). **Vide = mode `*` sans credentials** (OK si front/API même origine) |

### Tests exécutés (extraits des preuves)
- `Origin: https://evil.com` (mode défaut) → `Access-Control-Allow-Origin: *`, `credentials: None`.
- `Origin: https://agentready.io` (whitelist) → `Access-Control-Allow-Origin: https://agentready.io`, `credentials: true`.
- `Origin: https://evil.com` (whitelist) → **rejet** (`allow-origin: None`).

---

## ✅ Ticket #2 — Centralisation & Robustesse Gemini

### Constantes (source de vérité unique)
```python
GEMINI_PRIMARY_MODEL  = "gemini-3.6-flash"      # défaut production
GEMINI_FALLBACK_MODEL = "gemini-3.1-flash-lite"  # repli low-cost
GEMINI_MODELS = [GEMINI_PRIMARY_MODEL, GEMINI_FALLBACK_MODEL]
```
*Plus aucune chaîne de modèle en dur dans les fonctions.*

### Architecture du client & fallback
- `_get_gemini_client(api_key)` : point d'entrée unique : clé (requête ou `.env`), détection SDK, instanciation sécurisée.
- `generate_gemini_content` : boucle sur `GEMINI_MODELS`, renvoie `(response, model_used)` pour traçabilité.
- **Cascade dégradée (zéro 500)** quand aucun modèle ne répond / quota saturé :
  - Sur quota saturé : badge `✅ Mode Déterministe Certifié (Quota live saturé)` — `fallbackReason: "quota_exhausted"`
  - Sans clé configurée : badge `✅ Mode Déterministe Certifié (Zéro Clé Requise)`
  - Le score d'audit reste 100% déterministe (jamais affecté par le statut du live).

### Variables d'environnement
| Variable | Rôle |
|----------|------|
| `GEMINI_API_KEY` | Clé API Google. Absente → simulateur en déterministe transparent (aucun blocage), scan intact. |

---

## 🧭 État & santé du produit après Sprint P0 + P1

| Axe | Statut |
|-----|:------:|
| Retrait du StaticFiles racine (code & secrets inaccessibles) | ✅ |
| `.gitignore` hermétique (`leads.csv`, `*.pdf`, `.env*`, caches) | ✅ |
| Cobayes isolés (`tests/fixtures/`) | ✅ |
| Score 5 piliers pondérés PRD (20/25/20/20/15) + `weight` numériques | ✅ |
| Grille protocoles dégradée (plancher strict base absent = 5) | ✅ |
| Simulateur déterministe au scan synchrone (zéro LLM) | ✅ |
| Lead capture résiliente Postgres/Supabase + Slack + CSV backup | ✅ |
| Fix UX Trust (lead ≠ succès PDF) | ✅ |
| CORS durci (env, credentials découplés, méthodes restreintes) | ✅ |
| Gemini centralisé + fallback quota sans 500 | ✅ |

---

## ✅ Checklist de mise en production — Variables à brancher sur Railway

| Variable | Requise ? | Valeur attendue en prod | Notes |
|----------|:---------:|------------------------|-------|
| `GEMINI_API_KEY` | Oui (pour live) | Clé Google valide | Absente → simulateur en déterministe transparent (aucun blocage) |
| `DATABASE_URL` | Oui (leads) | DSN Postgres managé Railway/Supabase | Table `leads` auto-créée (`CREATE TABLE IF NOT EXISTS`) |
| `SLACK_WEBHOOK_URL` | Recommandé | Incoming webhook Slack/Discord | Alerte commerciale temps réel ; absent → backup CSV uniquement |
| `CORS_ORIGINS` | Non | `https://<domaine-front>` (ou vide si même origine) | Vide → `*` sans credentials (compatible same-origin) |
| `PORT` | Railway auto | 8000 par défaut | Géré par le Procfile/Railway |

> **Recommandation prod :** activer le plugin Postgres Railway (service managé, persistant) et brancher `DATABASE_URL` auto-injecté ; configurer le webhook Slack du canal de vente avant tout trafic réel.

---

## ⏭️ Prochains jalons (P2 — quand le flux semi-concierge a validé la valeur)
1. **Validation croisée E2E du tunnel complet.**
2. **Auth + Espace Client** (invitation, historiques, re-scans).
3. **Paywall Stripe** (Free / Pro 49 € / Agency 199 €) + quotas par plan.
4. **Dashboard monitoring récurrent** + scan en masse + PDF white-label agences.
