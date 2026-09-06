# ISSUE #3 (P1) — Durcir la config CORS (origines strictes / conformité navigateur)

## Contexte / Diagnostic
Dans `server.py` :
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Le combo `allow_origins=["*"]` avec `allow_credentials=True` est **non conforme aux navigateurs** : quand `allow_credentials` est actif, la valeur `Access-Control-Allow-Origin: *` est rejetée par les clients navigateurs (la spec exige une origine explicite). En pratique, certains appels cross-origin peuvent donc échouer ou être incohérents selon le client.

De plus, ouvrir l'API publique du scanner à toutes les origines (avec autorisation de toute méthode) expose l'endpoint `/api/scan` (qui fait du scraping à la demande) à n'importe quelle page web — risque d'abus / usage détourné.

## Correction cible
Homogénéiser le comportement cross-origin :
1. **Option recommandée pour un MVP auto-hébergé** : servir le frontend depuis la même origine que l'API (le projet monte déjà le static sans CORS nécessaire) → l'API publique de scan peut être servie sans `allow_credentials`, ce qui autorise `allow_origins=["*"]` sans credentials.
2. Ou, si des origines précises doivent être autorisées (front séparé), lister des origines explicites via variable d'env `CORS_ORIGINS` et n'activer `allow_credentials` que dans ce cas.

## Actions cible
- [ ] Découpler : `allow_credentials=True` uniquement si des origines explicites sont configurées ; sinon `allow_origins=["*"]` sans credentials.
- [ ] Conduire `allow_origins` depuis la config env (`CORS_ORIGINS`, format JSON ou CSV) au lieu d'un `*` en dur.
- [ ] Restreindre `allow_methods` aux méthodes réellement utilisées (`GET`, `POST`).
- [ ] Documenter le choix (même-origine vs origines configurées) dans le README/déploiement.

## Critères de validation
- [ ] `/api/scan` appelé depuis une origine configurée (ou same-origin) fonctionne avec credentials si besoin.
- [ ] Plus de `allow_origins=["*"]` + `allow_credentials=True` combinés.
- [ ] Comportement cross-origin cohérent vérifié au navigateur (console réseau sans erreur CORS).

## Fichiers concernés
- `server.py` → bloc `CORSMiddleware`
- `README.md` (documentation de la variable `CORS_ORIGINS`)
