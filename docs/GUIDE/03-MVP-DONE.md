# 🏁 AgentReady — MVP TERMINÉ & livrable (2026-09-06)

> Synthèse de clôture rédigée par Cline (architecte). Une seule branche `main`.
> **Tests : 16/16 verts** — CI GitHub Actions verte à chaque push.

---

## ✅ Ce qui est fonctionnel (le MVP)
1. **Audit « Agentic Readiness »** — scan d'une URL de fiche produit e-commerce, score **0-100 sur 5 piliers** (Crawl 20 / Schema 25 / Tokens 20 / Simulateur 20 / Protocoles 15) conforme au PRD.
2. **Rapport PDF white-label** téléchargeable (module `pdf_generator.py` dédié) + destination email.
3. **Capture de leads résiliente** (`lead_sink.py`) : Postgres transactionnel + webhook Slack + backup CSV ; UX « email conservé » transparente (TACHE/P0/P1).
4. **100 % déterminisme sans clé** : simulateur d'achat déterministe; cascade Gemini live si clé capitale.
5. **Durcissement anti-abus** :
   - Rate-limit fenêtré par IP → `/api/scan`, `/api/gemini/simulate-question`, `/api/lead`, `/api/report/pdf` (env configurables).
   - Garde-fous scanner : validation d'URL stricte **avant** fetch, rejet statuts d'erreur, rejet non-HTML (`415`), borne taille (`413`/troncature), timeout configurable.
   - **Anti-SSRF** : blocage IP privées/réservées/loopback/link-local/metadata (+IPv6), résolution DNS tolérante.
   - Validation d'email (400 propre, sans dépendance externe).
6. **Frontend** : page unique responsive, presets de démo, bandeau d'erreur backend explicites (4xx/5xx) en remplacement d'un faux fallback friction + transparence du repli « démo » réseau.
7. **Gouvernance** : CI GitHub Actions, dossier `docs/GUIDE/` (protocole archivé, état des lieux, roadmap, toutes les TACHE-01/02).

## 📌 Dernière action PROD restante (à faire par l'humain)
- **Redéployer Railway depuis `main`** pour intégrer le lot sécurité A5 (commit `bcccb71` : anti-SSRF, rate-limits lead/PDF, validation email). Le code est prêt+testé; le déploiement attendu met à jour `aiready-production-a6c0.up.railway.app`.

## ⚠️ Limites connues (à départir en P2, NON freinantes MVP)
- Rate-limit IP **mono-processus** : en multi-réplicas Railway les 429 sont seulement partiels → **Redis distribué** recommandé quand on passera multi-worker.
- Emails stockés localement: DB/Postgres optionnelle; un astreint RGPD devrait durcir l'hébergement en P2.
- Pas de build/minification front (Vite) ni de tests frontend automatisés.
- Le « tunnel réel » sur un site e-commerce réel (WAF/CSR) déjà démontré sur les presets démo; à confirmer par 1-2 scans réels en démo « client-ready ».
- Pas d'authentification / paywall / espace client — **bloc B** explicitement **gelé** (décision humaine requise sur grille tarifaire & fournisseur).

## 🧭 Coche finale DoD MVP
- [x] Scoring PRD + intégrité front testée.
- [x] Régressions automatisées (16 tests) + CI.
- [x] Sécurité raisonnable en production (CORS durci, anti-SSRF, rate-limits, hermétiques fichiers).
- [x] Déployable 1-clic Railway (configs présentes) — **prod mise à jour après redéploiement A5**.
- [x] Documentation de pilotage & état des lieux archivée sur `main`.
- [ ] *(Initiative commerciale)* décision tarif bascule P2 — à l'initiative de l'utilisateur.
