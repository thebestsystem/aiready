# ISSUE #5 (P0) — Fiabiliser la capture de leads : Postgres + notification temps réel

## Contexte / Diagnostic
Aujourd'hui, chaque lead (visiteur qui laisse son email pour le rapport PDF) est écrit dans **`leads.csv` sur le filesystem local** via `save_lead()` (`server.py`), appelé par `POST /api/lead` et par `POST /api/report/pdf`.

C'est P0 car c'est **notre seule source de revenus semi-concierge** : si le fichier local est sur un disque éphémère (Railway/Heroku redeploy = wipe), **on perd les emails** (la monnaie). Il faut une sortie résiliente **dès J0**.

## Décision d'architecture (actée par le cofondateur / l'équipe)
1. **Stockage persistant transactionnel → PostgreSQL managé (Railway, déjà provisionnable) ou Supabase.**
   Le lead est inséré de façon transactionnelle avec : `email`, `domain`, `product_name`, `score`, `status`, `hallucination_risk`, `source` (scanner vs PDF), horodatage serveur `created_at`. Le CSV local ne reste qu'un **backup** (jamais la seule source).
2. **Notification temps réel → Webhook Slack (ou Discord), `SLACK_WEBHOOK_URL`.**
   Dès qu'un prospect télécharge un PDF ou soumet une URL : alerte push avec ses coordonnées pour une relance sous 15 minutes (vitesse commerciale).
3. **Faille P0 « zéro perte » :** si le canal distant (webhook/DB) échoue → le lead n'est jamais perdu silencieusement : fallback écriture locale + log d'erreur explicite + retry léger.

## Contrat de données (cohérent avec `LeadRequest`)
Champs à pousser : `email`, `domain`, `product_name`, `score`, `status_label`, `hallucination_risk`, `source`. Data agrégée seulement (pas le JSON d'audit brut par défaut) ; stocker éventuellement une référence/lien.

## Actions cible
- [ ] Activer le plugin Postgres sur Railway (ou table Supabase) ; table `leads` avec index sur `created_at`, `email`.
- [ ] `.env` : `DATABASE_URL` / `SUPABASE_URL` + `SLACK_WEBHOOK_URL` (ajouter au `.env.example`, jamais commité).
- [ ] Créer un module unique de sortie lead (`lead_sink.py` / service) : insert DB transactionnel → alerte Slack (timeout court + retry léger) → écriture CSV de backup.
- [ ] `POST /api/lead` et `POST /api/report/pdf` appellent ce service. Ajouter `source` à `LeadRequest`, et un `created_at` côté serveur.
- [ ] Faille « zéro perte » : échec Slack/DB n'empêche pas la complétion HTTP côté client (le PDF se télécharge quand même), mais la persistance durable (disque fallback) est garantie côté serveur.

## Fix UX / Trust (front `js/app.js`, ~ligne 383)
Séparer **nettement** l'état d'enregistrement du lead du succès de génération du PDF (arbitrage acté) :
- Si le `fetch('/api/report/pdf')` réussit → afficher succès (lead enregistré + PDF téléchargé).
- S'il échoue → **message d'échec honnête + bouton de re-tentative** ; **ne plus afficher** « Vos informations ont toutefois été prises en compte » (fausse promesse, le serveur n'a rien reçu en cas d'échec réseau).
- Le succès du lead ne s'affiche **qu'après** un 2xx serveur.

## Critères de validation
- [ ] Simuler `POST /api/lead` → le lead apparaît dans Postgres/Supabase ET reçoit une alerte Slack, ET un backup CSV local écrit.
- [ ] Couper réseau / webhook invalide → le lead n'est **pas perdu** (disque + log d'erreur explicite).
- [ ] Aucun secret en dur ; tout passe par env ; `DATABASE_URL`/`SLACK_WEBHOOK_URL` non commités.
- [ ] (Postgres) requête simple d'historisation/listing des leads OK.
- [ ] Front PDF : l'état de succès du lead ne s'affiche que sur 2xx ; en cas d'échec → honnête + re-tentative possible.

## Fichiers concernés
- `server.py` (`save_lead`, endpoints `/api/lead`, `/api/report/pdf`)
- nouveau module (ex. `lead_sink.py`)
- `js/app.js` (état lead vs succès PDF)
- `.env.example`, `.gitignore`
