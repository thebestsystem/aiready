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
4. **Complétude de l'offre :** Vérification déterministe que la fiche contient tout ce qu'un agent IA doit lire (prix, stock, livraison, retour) pour répondre sans inventer.
5. **Protocoles Agentiques :** Validation et génération de fichiers `llms.txt`, manifestes `agent-card.json` et serveurs **Model Context Protocol (MCP)**.

---

## 🛠️ Stack Technique

### ⚡ Stack Actuelle (MVP de Production Déployé)
- **Backend & Moteur d'Audit :** Python 3.11+ avec **FastAPI**, **Uvicorn**, **httpx** (requêtes asynchrones avec protection SSRF stricte et rate-limiting mémoire par fenêtre glissante), **BeautifulSoup4** pour l'extraction sémantique (DOM, JSON-LD, microdata).
- **Frontend :** Single Page Application en **Vanilla JavaScript (ES Modules)**, design system CSS moderne (variables, responsive, dark glassmorphism, animations fluides), FontAwesome & icônes SVG.
- **IA & Simulation Agentique :** **Google GenAI SDK** (`google-genai` officiel, modèles `gemini-3.6-flash` & `gemini-3.1-flash-lite`), avec mode déterministe certifié haute fidélité sans clé pour le scan principal.
- **Génération de Rapports :** **ReportLab** (génération de rapports PDF professionnels et sécurisés contre les injections de balises XML).
- **Persistance & Intégrations :** **PostgreSQL** managé via `psycopg2-binary` (avec résilience et repli automatique sur stockage CSV local), webhook de notification **Slack/Discord** et envoi d'emails transactionnels **Resend**.

### 🚀 Roadmap / Stack Cible (P2 / V2)
- **Frontend :** Migration vers Next.js 15 (App Router), Tailwind CSS & Framer Motion.
- **Scanning Asynchrone à Grande Échelle :** Workers distribués avec Redis & BullMQ pour les audits multi-pages en file d'attente.
- **Rendu JavaScript Lourd :** Support Playwright / Headless Chromium pour les boutiques en rendu 100% Client-Side (CSR) complexe.

---

## 🚀 Démarrage Rapide Développeur (Onboarding)

Le projet est conçu pour être lancé instantanément, quel que soit l'environnement de développement :

### Option A : Windows (Lanceur 1-clic)
Double-cliquez sur `start.bat` ou lancez-le en invite de commandes :
```cmd
start.bat
```
> **Ce que fait le script :**
> - Détecte automatiquement l'environnement virtuel (`.venv`), Python système ou installation locale.
> - Détecte et configure automatiquement Node.js (`C:\node-v24-LTS` ou PATH) pour les outils frontend.
> - Initialise automatiquement le `.env` depuis `.env.example` s'il n'existe pas.
> - Installe les dépendances requises et démarre le serveur unifié sur `http://localhost:8000`.

### Option B : Mac / Linux
Rendez le script exécutable et lancez-le :
```bash
chmod +x start.sh
./start.sh
```

### Option C : Docker (Zéro installation requise)
Si vous disposez de Docker :
```bash
docker compose up
```
L'application démarre sur `http://localhost:8000` avec rechargement à chaud et persistance des données.

### Option D : Manuel (Environnement Virtuel Standard)
```bash
python -m venv .venv
# Sur Windows :
.venv\Scripts\activate
# Sur Mac/Linux :
source .venv/bin/activate

pip install -r requirements.txt
uvicorn server:app --host 127.0.0.1 --port 8000 --reload
```

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
