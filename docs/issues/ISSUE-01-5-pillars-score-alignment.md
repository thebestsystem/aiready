# ISSUE #1 (P0) — Aligner le calcul du score global sur les 5 piliers du PRD

## Contexte / Diagnostic
Le code (`server.py`) calcule actuellement le score global **uniquement sur 3 piliers** :
- Crawl & Access : 30 %
- Schema.org / JSON-LD : 40 %
- Pureté Sémantique & Tokens : 30 %

Les piliers du **AI Buyer Simulator** (`poids="Simulation"`) et des **Protocoles agentiques** (`poids="Protocoles"`) sont affichés dans le rapport mais **n'entrent pas** dans le score 0-100. Le PRD promet pourtant un score sur **5 piliers pondérés**. C'est une dissonance produit inacceptable (on vend 5 piliers, on en calcule 3).

## Règle cible (à implémenter, 100 % alignée PRD)
| # | Pilier | Poids |
|---|--------|:---:|
| 1 | Crawl & Access IA | 20 % |
| 2 | Schema.org / JSON-LD | 25 % |
| 3 | Pureté Sémantique & Tokens | 20 % |
| 4 | AI Buyer Simulator | 20 % |
| 5 | Protocoles Agentiques (llms.txt & MCP) | 15 % |

`total_score = (crawl*0.20) + (schema*0.25) + (semantic*0.20) + (simulator*0.20) + (proto*0.15)`, clampé à [5,100].

## Contraintes d'exécution
- **Pilier 4 (AI Buyer Simulator)** : la note doit rester **100 % déterministe** (heuristique standardisée sur l'exhaustivité des données critiques : prix, livraison, retour, stock). **0 appel LLM synchrone** dans le scan. Gemini, s'il est configuré, enrichit seulement l'explication qualitative et le log — jamais la note de base.
- **Pilier 5 (Protocoles)** : la note intègre les 15 %. Le score de base (ex: 0 sans llms.txt, 70 avec llms.txt détecté) doit être revu pour être **proportionnel** et non abrupt (binaire 0 ↔ 70 déséquilibre la moyenne). Proposer une grille dégradée.
- **Champ `weight`** des 5 `PillarScore` : passer de libellés libres (`"Simulation"`, `"Protocoles"`) à des pourcentages numériques (`"20%"`, `"15%"`) pour cohérence avec le front.
- Mettre à jour le **libellé UI** des piliers pour qu'il reflète le poids réel (le front affiche la pondération).

## Critères de validation
- [ ] Pondération `docs/PRD.md` == pondération `server.py`.
- [ ] URL sans `llms.txt` vs même URL avec `llms.txt` → la différence de score total est exactement de `0.15 × Δ(proto_score)`.
- [ ] `weight` affiché est numérique (20/25/20/20/15).
- [ ] Scanner synchrone ne déclenche **aucun** appel réseau vers l'API Gemini.

## Fichiers concernés (estimation)
- `server.py` → `scan_url()`, calcul `total_score`, `PillarScore`, pondérations.
- `docs/PRD.md` (déjà juste — sert de référence).
- Composant frontend affichant la pondération des piliers (`index.html`, `js/app.js`).
