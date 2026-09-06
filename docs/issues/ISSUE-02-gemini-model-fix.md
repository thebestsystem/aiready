# ISSUE #2 (P1) — Harmoniser les identifiants de modèles Gemini sur les références stables actuelles

## ⚠️ Correction du diagnostic initial (important)
Une note datée : ce repo vit dans un contexte temporel où les modèles Gemini **3.x sont stables et courants** (doc Google GenAI, mise à jour 2026-09-04). Les identifiants `gemini-3.6-flash` et `gemini-3.1-flash-lite` présents dans le code **ne sont pas des « chaînes fantômes »** — ce sont des modèles **stables réels**. Ma première hypothèse (basculer sur `gemini-2.5-flash` / `2.0-flash`) est **caduque** : ces 2.x sont dépréciés / éteints dans ce contexte. L'issue porte donc non sur un renommage massif, mais sur la **cohérence, la centralisation et l'actualisation** des références. **Ne pas « corriger » vers des modèles 2.x.**

## Vrais problèmes à résoudre
1. **Chaînes de modèles en dur, éparpillées** et légèrement incohérentes :
   - `generate_gemini_content()` boucle sur `["gemini-3.1-flash-lite", "gemini-3.6-flash"]` (lite en premier, flash ensuite).
   - `gemini_status()` et `simulate_question()` renvoient au front un `"model": "gemini-3.6-flash"` codé en dur.
   - Risque réel : les identifiants **stables évoluent** (ex. `gemini-3.8-flash` est déjà disponible). Les chaînes en dur rendent toute mise à jour fragile et la réponse au front peut diverger du modèle réel.
2. **Sélection de modèle non alignée sur l'usage** : pour un `AI Buyer Simulator` qualité production, préférer un modèle **stable récent** comme défaut (`gemini-3.6-flash`, voire `gemini-3.8-flash` si adapté au besoin), avec un **fallback correct**.

## Actions cible (spécification ferme)
- [ ] **Constantes modulaires** dans `server.py` (haut de fichier, à côté de la config) :
      ```python
      GEMINI_PRIMARY_MODEL   = "gemini-3.6-flash"   # défaut production (stable)
      GEMINI_FALLBACK_MODEL  = "gemini-3.1-flash-lite"  # fallback (stable, coût bas)
      GEMINI_MODELS = [GEMINI_PRIMARY_MODEL, GEMINI_FALLBACK_MODEL]
      ```
- [ ] **Factorisation du client SDK** : créer `_get_gemini_client(api_key)` (une seule instanciation `genai.Client`, une seule zone de gestion d'erreurs) et faire passer `generate_gemini_content()`, `gemini_status()`, `simulate_question()` par ces constantes + ce client.
- [ ] **Sécuriser les erreurs de quota/dépréciation** : si le modèle primaire renvoie `RESOURCE_EXHAUSTED` / modèle inconnu → bascule automatique sur le fallback + logguer. Ne jamais faire crasher le scan : en cas d'échec définitif, descendre proprement vers le fallback déterministe (comportement actuel, à conserver).
- [ ] **Réponse `model` du front cohérente** : `gemini_status()` et `simulate_question()` renvoient l'identifiant réellement utilisé / proposé (via les constantes), pas une chaîne séparée en dur.
- [ ] Aucune occurrence de chaîne de modèle hors de la constante `GEMINI_MODELS`.

## Critères de validation
- [ ] Exactement **un** endroit définit les identifiants (constante). Plus aucune chaîne `gemini-...` en dur dans une fonction.
- [ ] `POST /api/gemini/test` avec clé valide → `{"ok": true, "model": "gemini-3.6-flash"}`.
- [ ] Quand le primaire est volontairement mis en erreur, le fallback `gemini-3.1-flash-lite` est tenté (traçable dans les logs).
- [ ] Le scan synchrone ne plante jamais sur une erreur Gemini (repli déterministe conservé).

## Fichiers concernés
- `server.py` → `generate_gemini_content()`, `gemini_status()`, `simulate_question()`, nouveau helper client.
