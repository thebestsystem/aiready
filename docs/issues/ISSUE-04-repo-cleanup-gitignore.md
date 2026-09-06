# ISSUE #4 (P0) — Dépolluer la racine du repo + fiabiliser `.gitignore`

## Contexte / Diagnostic
Des scripts de dev exploratoires / cobayes e-commerce traînent **à la racine** du repo et seraient livrés en prod :
- `debug_welcomeoffice.py`
- `inspect_welcomeoffice.py`
- `test_scan.py`, `test_ecommerce_scan.py`, `test_image_scoring.py`, `test_img_scan.py`, `test_jabra_scan.py`

(`welcomeoffice`, `jabra` étaient nos cobayes de fiches produits complexes — B2B / catalogues lourds.) Laisser ces fichiers à la racine d'un repo que l'on présente à des clients nuit à la crédibilité et peut laisser fuiter des URLs/identifiants de test dans `server.py` (le répertoire est par ailleurs monté en static). Il faut une organisation nette et un `.gitignore` propre.

## Correction cible
1. **Déplacer / organiser** les scripts de test vers un dossier `tests/` (ou `tests/fixtures/`) — ou les archiver hors du build de prod. Rien de tel ne doit rester à la racine.
2. **Nettoyer le code de prod** (`server.py`) de toute référence/trace pontée vers ces cobayes (URLs de démo, chemins `welcomeoffice`, données dures).
3. **Remettre le `.gitignore` au carré** pour exclure :
   - `leads.csv` (données clients/visiteurs — **ne doit JAMAIS être commité** ; fichiers générés, sécabilité)
   - secrets env : `.env`, `.env.local`
   - caches Python : `__pycache__/`, `*.pyc`, `.venv/`, `venv/`
   - `.DS_Store`, logs, fichiers d'upload temporaires.

## Points d'attention (Sécurité)
- Vérifier qu'aucune **clé API** (ex. `GEMINI_API_KEY`) n'est embarquée en dur dans `server.py` ou scripts — uniquement via env.
- Confirmer qu'aucune donnée de cobaye (URLs d'e-commerçants réels de test) ne subsiste dans le code livrable ou le README.
- `leads.csv` ne doit pas être poussé sur le repo s'il contient des emails de visiteurs réels.

## Critères de validation
- [ ] Racine du repo : uniquement fichiers de prod + `docs/` + assets requis (aucun `debug_*`, `test_*`, `inspect_*`).
- [ ] `.gitignore` couvre env/secrets/caches/leads.csv.
- [ ] `git status` propre après suppression; les fichiers déplacés ne sont pas retracés dans le build static.
- [ ] Un scan réussi de production ne référence plus aucun nom de cobaye.

## Fichiers concernés
- Racine du projet (fichiers `debug_*.py`, `test_*.py`, `inspect_*.py`)
- `.gitignore`
- `server.py` (traces parasites éventuelles)
- (Déplacement vers `tests/` le cas échéant)
