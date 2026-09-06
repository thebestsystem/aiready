# ✅ TACHE-01 — Rate-limit anti-abus sur `/api/scan` et `/api/gemini/simulate-question`

> **Statut :** à faire (proposée par Cline/VPS, source `docs/ROADMAP-MVP.md` P1-3 "à ouvrir").
> **Portée :** UNE seule livraison cohérente — ne **rien** toucher d'autre (pas de refactor, pas d'UI).
> **Exécutant :** extension Cline dans Antigravity, branche `wip/`.

---

## 🎯 Objectif
Empêcher qu'un tiers épuise gratuitement le scanner (coût réseau/CPU + risque d'abus) par un nombre raisonnable de scans par IP, avant tout trafic réel. Simple, sans rajouter de dépendance lourde, **sans casser la démo** (l'utilisateur/front qui fait des tests ne doit pas être bloqué par ses propres essais légitimes).

## ▸ Contexte technique (vérifié par Cline/VPS)
- Le serveur est **FastAPI + uvicorn** monté dans `server.py`. Il n'a **pas** de middleware rate-limit actuellement (vérifié : aucun throttle/cooldown).
- Le front, en mode démo, appelle son **propre** `/api/scan` en boucle légitime (scanner de démonstration). Un rate-limit trop bas casserait la démo. Le backend est **mono-utilisateur** en l'état (front et API servis en même origine). Il ne faut donc PAS étouffer par erreur un usage de démonstration légitime.
- `ts` se lit via `req` (FastAPI injecte le `Request`) : **adresse IP** dispo via `request.client.host`. Derrière un reverse proxy (Railway), attention aux en-têtes `X-Forwarded-For` — à gérer proprement (utiliser le 1er ou le dernier selon la confiance, documenter le choix) sans créer de faille de spoofing.
- Deux endpoints coûteux à protéger : `POST /api/scan` (lourd, fetch HTTP sortant) et `POST /api/gemini/simulate-question` (appel LLM si clé).

## 🎯 Spécification de la limite (proposition Cline/VPS — ajustable par l'utilisateur)
- Fenêtre glissante en **mémoire** (pas de Redis/DB pour ce stade — le monoprocessus uvicorn le permet ; un note DOC utilisera Redis quand on passera multi-worker/P2).
- **Par IP** :
  - Réseau de scan lourd → **configurable via env** `SCAN_RATE_LIMIT` (défaut p.ex. `10`) scans par fenêtre `SCAN_RATE_WINDOW_SECONDS` (défaut p.ex. `60` s).
  - Endpoint simulateur (LLM coûteux) → limite **plus basse** configurable `SIM_RATE_LIMIT` (défaut p.ex. `5`/60s).
- Réponse en dépassement → **HTTP 429** avec en-têtes standard `Retry-After` et un corps JSON clair `{"detail": "...", "retry_after": N}`. Le front doit pouvoir l'afficher sans crash.

## 📄 Fichiers concernés
- `server.py` : ajout d'un mécanisme de fenêtre glissante en mémoire (dict IP→timestamps ou structure dédiée), utilitaire d'extraction d'IP (`request.client.host` + `X-Forwarded-For` documenté), et application comme **dépendance FastAPI (`Depends`)** sur les 2 endpoints, ou middleware.
- 2 nouvelles **fonctions de test** à la fin de `tests/test_e2e_pipeline.py` (mêmes conventions unittest) prouvant : (1) l'IP sur la limite n'est pas bloquée, (2) l'IP au-delà reçoit 429, (3) une autre IP reste OK (isolée).

## ⚙️ Règles d'exécution (contraintes)
1. **Aucune nouvelle dépendance `requirements.txt`** sauf accord explicite (on veut rester minimal). Si un package est absolument nécessaire, le signaler dans le commit, ne pas l'ajouter seul → sans accord il faut implémenter à la main (léger, ~40 lignes suffisent).
2. Rester **cohérent avec la config par env** : respecter le style déjà utilisé (`os.getenv`. Lire les constantes existantes autour de la config CORS).
3. **Ne pas casser la démo front légitime** : le simulateur/génération n'est pas appelé en boucle lourde par un vrai usage, mais garder des seuils assez hauts et **par défaut assez permissifs** pour ne pas bloquer un prospect qui démontre.
4. Garantir la **régression** : la suite existante `tests/test_e2e_pipeline.py` doit rester **verte** après ton changement.
5. Effacer proprement les fenêtres expirées (éviter une fuite mémoire en croissance infinie : purger les IP inactives).

## ✔️ Definition of Done (critères de validation — Antigravity doit tous les passer)
- [ ] `POST /api/scan` répond **429** (JSON + `Retry-After`) quand une même IP dépasse la limite ; répond normalement en deçà.
- [ ] `POST /api/gemini/simulate-question` est protégé par SA limite (plus stricte), testé.
- [ ] Deux IPs distinctes sont traitées **indépendamment** (testé).
- [ ] La limite et la fenêtre sont **configurables par env** avec valeurs par défaut documentées dans une note.
- [ ] Chaque endpoint protégé refuse de manière **non-fatale** (le front n'a pas de 500).
- [ ] Nouvelles fonctions de tests ajoutées et **la suite complète passe**.
- [ ] Commit(s) propre(s), message clair, sur branche `wip/`, SANS toucher à `docs/GUIDE/`.

## 🔍 Points d'attention pour Antigravity (à relire avant de coder)
- Le `Request` FastAPI est fourni même en POST ; il faut l'ajouter en paramètre de la fonction endpoint ou de la dépendance.
- Ne pas mettre le rate-limit **avant** le middleware CORS d'une façon qui empêcherait les preflight — tester les options.
- Documenter le choix de parsing `X-Forwarded-For` (faille de spoofing si on se fie aveuglément au client) dans un commentaire court.

## ▶️ Comment lancer et vérifier (obligatoire avant de déclarer terminé)
```bash
# 1. (si besoin) installer les dépendances du projet
python3 -m pip install -r requirements.txt

# 2. lancer LA SUITE COMPLÈTE de tests (tes 2 nouveaux tests + les 6 existants)
cd <racine-du-repo>
python3 -m unittest discover -s tests -p "test_*.py" -v
```
Toute la suite doit être **verte** (`OK`). Les tests sont en `unittest` (pas pytest) : ils s'exécutent sans clé Gemini ni base de données réelle (montage par mock), donc aucun `.env` requis.
