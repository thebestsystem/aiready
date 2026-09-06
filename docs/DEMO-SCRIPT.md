# 🎬 Script de démo AgentReady — mot à mot

**Durée : ~3 min · Support : le site en prod (live) — `https://aiready-production-a6c0.up.railway.app/`**

---

## Avant la démo (5 min, en amont)

- [ ] Onglet prêt sur la prod.
- [ ] URL cible **pré-scannée et vérifiée** (ex. `storelashes.fr` → **53/100**).
- [ ] PDF de démo déjà généré, prêt à afficher sans attendre.
- [ ] Moins de 10 scans dans la dernière minute (sinon 429 rate-limit).

---

## 0. Le hook (20 s)

> « Une question simple : quand ChatGPT, Perplexity ou Gemini recommandent un produit à un acheteur, est-ce qu'ils recommandent **le vôtre** — ou une version hallucinée de son prix et de son stock ? »

---

## 1. Le scan en direct (40 s)

*(Collez l'URL du prospect dans le champ, lancez le scan.)*

> « On vérifie ça en direct, sur votre propre site. Je colle l'URL… et voilà. »

*(Le score s'affiche.)*

> « Votre fiche obtient **53 sur 100** en "préparation aux agents IA". Traduction : un agent d'achat qui la visite aujourd'hui **lit mal vos informations**. »

---

## 2. Les 5 piliers (60 s)

*(Déroulez les cartes une par une, en lisant les vrais chiffres du scan.)*

> « On note 5 piliers :
>
> 1. **Accès robots (20 pts)** → **100/100** : votre `robots.txt` laisse passer les bots IA, très bien.
> 2. **Données structurées Schema.org (25 pts)** → **25/100** : c'est *ici* que ça casse. Prix et stock ne sont pas déclarés en JSON-LD, donc l'agent les **devine**.
> 3. **Efficacité tokens (20 pts)** → OK, votre page est lisible.
> 4. **Simulateur d'achat IA (20 pts)** → le prix est lisible, mais le stock et la politique de retour ne sont pas structurés : **risque d'hallucination**.
> 5. **Protocoles IA / llms.txt (15 pts)** → **5/100** : pas de `llms.txt`, pas d'endpoint MCP. C'est l'équivalent de ne pas être référencé — mais pour les agents. »

---

## 3. Le rapport PDF + la capture (30 s)

> « Et tout ça, vous l'emportez : le rapport PDF détaillé, ligne par ligne, avec exactement quoi corriger. »

*(Affichez / téléchargez le PDF.)*

> « Laissez-moi votre email, je vous l'envoie avec le suivi. »

*(Capture de l'email → la notification part en temps réel.)*

---

## 4. Le close (30 s)

> « Ce scan gratuit vous dit **où** vous perdez. Si vous voulez, je fais le **fix complet** : JSON-LD corrigé, `llms.txt`, endpoint MCP, en une passe. C'est un accompagnement manuel — je vous fais un devis. »

---

## 🛟 Filets de sécurité (si ça dérape)

- **Scan « aveugle » / erreur sur site protégé (Cloudflare, DataDome)** → « Votre site a une protection anti-bot. C'est exactement le signe qu'il bloque aussi les agents IA. » *(basculez sur le preset `storelashes.fr`, qui marche à coup sûr.)*
- **429 rate-limit** → « On a scanné plusieurs URL à l'instant, je laisse passer 30 secondes. »
- **« C'est quoi un agent IA ? »** → « ChatGPT Search, Perplexity Shopping, Gemini : les assistants qui achètent à la place de l'utilisateur. S'ils lisent mal votre fiche, ils recommandent un concurrent. »
- **« Vous êtes sûrs du score ? »** → « Le score est 100 % déterministe et reproductible à l'identique sur la même URL. Pas d'IA dans la note : zéro variance. »
