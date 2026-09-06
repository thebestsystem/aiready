# 🎛️ PROTOCOLE DE PILOTAGE — Cline VPS → Extension Cline dans Antigravity

> **Auteur du guide :** Cline (agent orchestrateur, VPS `vps-cb35549c`).
> **Exécutant :** Extension Cline lancée À LA MAIN par l'utilisateur dans **Antigravity** sur son PC.
> **Canal :** branche Git `guide/` (moi) ⟷ branche Git `wip/` (Antigravity) sur le repo `github.com/thebestsystem/aiready`.

---

## 🧭 Division des rôles (IMPORTANT — à relire à chaque tâche)

| Rôle | Qui | Ce qu'il fait |
|------|-----|---------------|
| **Architecte / Guide** | **Cline (VPS)** | Décide du *quoi* et du *pourquoi*. Rédige les `TACHE-*.md`, définit les critères de validation (DoD), passe en revue, teste, valide, met à jour la roadmap. **Il ne touche jamais directement au code feature.** |
| **Exécutant** | **Extension Cline (dans Antigravity)** | Décide du *comment*. Lit la tâche active, l'implémente dans le code, pousse proprement sur `wip/`, signale quand c'est fait. |
| **Décideur final** | L'utilisateur (humain) | Arbitre, donne le "go", valide la stratégie produit. |

L'utilisateur est **le relais** : il colle à Antigravity le prompt de démarrage de tâche (fichier `PROMPT-EXECUTANT.md`), puis m'annonce ici (`vps-cb35549c`, conversation Telegram) quand Antigravity a poussé sa branche.

---

## 🔁 Boucle de travail (cycle complet)

```
 [1] Cline(VPS) rédige/valide TACHE-N.md  ───►  pousse sur guide/
                                                      │
 [2] Utilisateur copie PROMPT-EXECUTANT.md (une tâche)
     et le colle dans l'extension Cline d'Antigravity  ◄─── lit guide/
                                                      │
 [3] Antigravity exécute, commit sur wip/, pousse    ───►  branche wip/
                                                      │
 [4] Utilisateur (Telegram) : « TACHE-N prête »      ───►  Cline(VPS)
                                                      │
 [5] Cline(VPS) pull wip/, test, révision, verdict    ───►  met à jour guide/
                                                      │
 [6] retour en [1] pour TACHE-N+1   (ou demande de correctifs)
```

Règle d'or anti-conflit : **Cline (VPS) n'écrit QUE dans `docs/GUIDE/`** ; Antigravity n'écrit **QUE** dans le code feature (plus mises à jour de tests). Si Antigravity doit corriger du guide, il le signale dans son commit, il ne le réécrit pas.

---

## 📁 Ce que contient `docs/GUIDE/`

| Fichier | Rôle |
|---------|------|
| `00-COMMENT-UTILISER.md` | Ce protocole (le présent fichier). |
| `01-PROJET-ETAT-DES-LIEUX.md` | Synthèse "où en est Aiready" (générée par Cline/VPS). |
| `02-ROADMAP-EXECUTION.md` | Liste ordonnée des tâches restantes → découpées en `TACHE-*`. |
| `TACHE-<N>-<slug>.md` | Une tâche exécutable, autonome, avec critères de validation. |
| `PROMPT-EXECUTANT.md` | Prompt **unique** à coller dans Antigravity pour démarrer une tâche |

---

## ✅ Quand utiliser ce dossier
Dès que l'utilisateur veut que **je guide** l'implémentation pendant qu'**Antigravity code** sur son PC. Le dossier `docs/GUIDE/` est versionné (branche `guide/`) pour garantir la traçabilité et la reprise en cas de coupure.
