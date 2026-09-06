# AgentReady — One-pager co-founder

> **Rendre les boutiques e-commerce lisibles par les agents IA.**

## Problème

Les agents d'achat IA (ChatGPT Search, Perplexity Shopping, Gemini) deviennent un canal de vente majeur : le trafic de recommandation issu de l'IA générative a bondi de **+805 % en un an**. Mais quand une fiche produit n'a pas de données structurées, **l'agent ne voit pas le produit, ou hallucine son prix/stock** → vente perdue, invisible pour le marchand. C'est le nouveau « SEO invisible ».

## Solution

**AgentReady** scanne une URL et note la *préparation aux agents IA* sur **100 points / 5 piliers** (accès robots · Schema.org · efficacité tokens · simulateur d'achat · protocoles llms.txt/MCP), puis produit un **rapport PDF** avec le correctif ligne à ligne.

**Monétisation en 3 temps :**
1. **Scanner gratuit** (lead magnet) — capture d'email.
2. **Packs manuels « mise en conformité » 500–1 500 €** — JSON-LD corrigé + `llms.txt` + endpoint MCP.
3. **SaaS de monitoring 49–199 €/mois** (re-scan récurrent, alertes de régression).

## Traction (état réel, sans fard)

- **En production** : scan réel en 2 s, PDF, capture de lead + notification email (Resend) + persistance Postgres.
- **Preuve sur de vrais sites** : `storelashes.fr` 53/100 · `macoque.com` 55/100 · `le-bourguignon.fr` 53/100 — le problème se voit en direct.
- **Ingénierie sérieuse** : 21 tests automatisés + CI, anti-SSRF (dont NAT64), rate-limiting, fallback IA sans 500.
- **Outreach lancé** : premiers emails de prospection envoyés (3+ prospects FR).
- **0 client payant à date** — validation commerciale en cours (assumé).

## Ask

Je cherche un co-founder **complémentaire** pour passer du « MVP qui marche » à la machine commerciale :

- **Profil A — technique** : headless browser (sites lourds/WAF), Redis, espace client + Stripe.
- **Profil B — business/GTM** : owner la prospection et la vente des packs 500–1 500 €, process d'outreach, conversion.

**Contrepartie** : equity **[X] %** avec vesting, à discuter (pas de salaire à ce stade).
