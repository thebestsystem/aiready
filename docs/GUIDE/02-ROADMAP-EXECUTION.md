# 🗺️ Roadmap d'exécution Aiready — plan piloté Cline(VPS) → Antigravity

> Pilote de travail généré le 2026-09-06. La **priorité est décidée par l'utilisateur.** Chaque ligne devient une `TACHE-*.md` autonome exécutable par Antigravity.
> Tableau de bord : `✅ fait` · `▶️ en cours` · `⏳ à faire` · `⛔ bloqué/manque info`

---

## 📍 Choix de périmètre immédiat (proposition Cline/VPS)
Vu la stratégie **semi-concierge/high-ticket d'abord** (J0–J60) explicitée dans `ROADMAP-MVP.md`, la monnaie = **leads irréprochables** + **démo qui tient debout face à un prospect pointilleux**. Le produit P0/P1 est déjà solide. Deux familles de travaux se distinguent :

- **A. Trempoline de crédibilité (pré-vente) :** durcir l'anti-abus + garantir la fiabilité avant tout trafic réel.
- **B. Monétisation P2 (post-validation du flux manuel) :** auth, espace client, Stripe, monitoring récurrent.

**Recommandation Cline/VPS : on attaque d'abord la Famille A, lot par lot** — car elle est indispensable à une vente propre, indépendante de décisions produit lourdes (Stripe), et qu'elle renforce le "0 variance, 0 hallucination" promis. La B ne démarre que si l'utilisateur confirme la validation du flux manuel.

---

## 🔵 Famille A — Fiabiliser avant de vendre

| # | Lot | Découpage | Priorité | Statut |
|---|-----|-----------|:--------:|:------:|
| A1 | **Rate-limit anti-abus** sur `/api/scan` + simulateur | `TACHE-01-ratelimit.md` (`P1-3`) | Haute | ✅ TACHE-01 (8/8 tests, livrée sur `main`) |
| A2 | **Verrouillage durée/limites scanner** (timeouts, taille domaine, URL non-HTML) | `TACHE-02-scanner-hardening.md` | Moyenne | ✅ TACHE-02 (14/14 tests, livrée sur `main`) |
| A3 | **Bouclage prod réel** : vérifier déploiement Railway + variables d'env + premier scan de démo "client-ready" | à découper (requiert accès déployeur) | Haute | ⏳ bloqué accès |
| A4 | **UX erreurs backend explicites** (4xx/5xx affichées au lieu d'un faux fallback friction + transparence mode démo) | `PRD` note d'installation front | Moyenne | ✅ TACHE-03 (14/14 tests, livrée sur `main`) |

## 🟠 Famille B — Monétisation P2 (après validation du manuel)

| # | Lot | Découpage | Statut |
|---|-----|-----------|:------:|
| B1 | **Auth + Espace Client** (invitation, historiques d'audits, re-scans) | à découper | ⏳ gelé |
| B2 | **Paywall Stripe** (Free / Pro 49€ / Agency 199€) + quotas par plan + webhooks | à découper | ⏳ gelé |
| B3 | **Dashboard de monitoring récurrent** (re-scan périodique + alerte régression de score) | à découper | ⏳ gelé |
| B4 | **Scan en masse + export** + **PDF white-label** pour agences | à découper | ⏳ gelé |

> ⚠️ **Bloc B2** : exige au préalable une décision de l'utilisateur sur la grille tarifaire PRD et le fournisseur de paiement (Stripe ?) — rien de câblé avant.

---

## 📋 Comment une tâche est "prête pour Antigravity"
1. Cline (VPS) écrit `TACHE-<N>-<slug>.md` = **une seule livraison cohérente** (objectif, fichier touchés, règles, tests, critères de validation "Definition of Done").
2. L'utilisateur colle `docs/GUIDE/PROMPT-EXECUTANT.md` (texte de lancement) suivi du chemin de la tâche dans Antigravity.
3. Antigravity implémente sur sa branche `wip/` et pousse. L'utilisateur me prévient (Telegram).
4. Cline (VPS) **pull**, **teste** (lance la suite E2E), **révision** → verdict + `TACHE-N+1`.
