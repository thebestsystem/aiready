# 🤖 AgentReady (AIReady Commerce)

> **"Is your e-commerce store invisible to AI buyers? Test, optimize, and monetize the Agentic Commerce wave."**

**AgentReady** est la plateforme SaaS d'audit, de simulation et d'optimisation technique pour rendre les fiches produits e-commerce découvrables, compréhensibles et achetables par les agents IA autonomes (ChatGPT Search, Perplexity Shopping, Google Gemini, Claude Web Agents, OpenAI Operator).

---

## 📚 Documentation du Projet

Toute la stratégie, l'analyse de marché et les spécifications techniques du produit sont documentées dans le dossier `/docs` :

- 📊 **[Analyse de Marché & Concurrence](./docs/MARKET_ANALYSIS.md)** : Données 2026, croissance du trafic IA, benchmark concurrentiel détaillé (Shopify Scanner, FoundGPT, Verity, Profound) et notre positionnement "Blue Ocean".
- 📋 **[Product Requirements Document (PRD)](./docs/PRD.md)** : Spécifications fonctionnelles complètes, les 5 piliers de scoring (0 à 100), architecture technique, protocoles IA (`llms.txt`, MCP), pricing et roadmap MVP.
- 💬 **[Archive de la Discussion Stratégique](./docs/CHAT_ARCHIVE.md)** : Transcription intégrale des échanges ayant défini la vision et les fondations du produit.

---

## 🎯 Les 5 Piliers d'Évaluation AgentReady

```
                                  [ AGENTIC READINESS SCORE ]
                                             (0 - 100)
                                                 │
      ┌──────────────────┬───────────────────────┼──────────────────────┬──────────────────┐
      ▼                  ▼                       ▼                      ▼                  ▼
1. Crawl & Access  2. Semantic Schema   3. Token Efficiency    4. Intent & FAQs   5. Actionability (MCP)
  (Robots, WAF,      (JSON-LD, Offers,       (Clean Markdown,       (Answers specs,     (llms.txt, API,
   Rendering)          Variants, Stock)        Zero Noise)            Anti-Hallucinate)   Cart Endpoints)
```

1. **Crawl & Accessibilité IA :** Analyse des directives `robots.txt` (GPTBot, ClaudeBot, PerplexityBot), blocage WAF (Cloudflare/DataDome) et détection SSR vs CSR.
2. **Données Structurées (Schema.org) :** Validation rigoureuse du JSON-LD `Product`, `Offer`, variantes, stocks temps réel et politiques de retour/livraison.
3. **Pureté Sémantique & Efficacité Tokens :** Nettoyage de la pollution DOM/scripts et mesure du coût en tokens pour les LLMs.
4. **AI Buyer Simulator :** Simulation de requêtes d'achat réelles via LLM (Gemini API) pour évaluer la recommandabilité et détecter le risque d'hallucination.
5. **Protocoles Agentiques :** Validation et génération de fichiers `llms.txt`, manifestes `agent-card.json` et serveurs **Model Context Protocol (MCP)**.

---

## 🛠️ Stack Technique Cible

- **Frontend :** Next.js 15 (App Router), Tailwind CSS, Framer Motion, Lucide Icons.
- **Backend & Scanning Engine :** Python (FastAPI) / Node.js, Playwright (Headless browser), Cheerio.
- **IA & Évaluation Sémantique :** Google Gemini API (Interactions API / Structured Outputs).
- **Protocoles Agentiques :** Serveur Model Context Protocol (MCP) + Générateur `llms.txt`.
- **Base de Données & Cache :** PostgreSQL (Prisma/Drizzle) + Redis (Queue BullMQ).

---

---

## ☁️ Déploiement Cloud (Railway / Render)

Le projet est configuré pour être déployé en 1 clic sur **Railway** (ou **Render**) avec son serveur unifié FastAPI (Backend API + Frontend statique) :

1. **Créer un dépôt GitHub** (privé ou public) nommé par exemple `agent-ready`.
2. **Lier le projet local à GitHub :**
   ```bash
   git remote add origin https://github.com/VOTRE_COMPTE/agent-ready.git
   git push -u origin main
   ```
3. **Sur Railway :**
   - Cliquez sur **New Project** > **Deploy from GitHub repo**.
   - Sélectionnez votre dépôt `agent-ready`.
   - Railway détecte automatiquement le `Procfile` et `railway.json`.
   - Dans **Variables**, ajoutez optionnellement votre `GEMINI_API_KEY`.
   - Dans les paramètres réseau (**Settings > Networking**), cliquez sur **Generate Domain** pour obtenir votre URL publique HTTPS gratuite.
