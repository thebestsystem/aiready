/* ==========================================================================
   AGENTREADY - Mock Data & Audit Engine Presets
   ========================================================================== */

export const AUDIT_PRESETS = {
  blind: {
    domain: "mystore-vintage.com/products/noise-canceling-nc700",
    name: "MyStore Fashion & Tech (Standard Shopify)",
    image: "assets/product_human_view.jpg",
    score: 38,
    status: "blind",
    statusLabel: "Agent Blind (Inaudible pour l'IA)",
    statusBadgeClass: "badge-blind",
    summary: "Ce site bloque les crawlers IA via Cloudflare WAF, souffre d'un balisage Schema.org incomplet et oblige les LLMs à dépenser +5 800 tokens par analyse, provoquant 40% de réponses hallucinées.",
    brokenItems: [
      {
        title: "Blocage WAF / Robots.txt actif sur GPTBot et ClaudeBot",
        impact: "Les agents IA ChatGPT Search et Perplexity reçoivent une page de challenge captcha 403 et ne peuvent pas indexer votre offre.",
        severity: "critical"
      },
      {
        title: "Microdonnées Schema.org Offer & Stock inexistantes",
        impact: "Aucun prix numérique ni stock en direct certifié. Les agents acheteurs refusent d'ajouter au panier.",
        severity: "critical"
      },
      {
        title: "Pollution DOM extrême (5 840 tokens par visite)",
        impact: "Scripts tiers et trackers inutiles qui saturent la mémoire de contexte des LLMs.",
        severity: "warning"
      }
    ],
    rawJsonLd: `<!-- ❌ AUCUN BALISAGE SCHEMA.ORG DÉTECTÉ -->
<!-- Les crawlers de ChatGPT, Gemini et Perplexity voient une page muette. -->
<script>
  window.ShopifyAnalytics = window.ShopifyAnalytics || {};
  // Microdonnées absentes du rendu serveur
</script>`,
    fixedJsonLd: `<script type="application/ld+json">
{
  "@context": "https://schema.org/",
  "@type": "Product",
  "name": "MyStore Vintage NC-700",
  "sku": "MSV-NC700-01",
  "offers": {
    "@type": "Offer",
    "price": "249.00",
    "priceCurrency": "EUR",
    "availability": "https://schema.org/InStock",
    "shippingDetails": {
      "@type": "OfferShippingDetails",
      "shippingRate": {
        "@type": "MonetaryAmount",
        "value": "0.00",
        "currency": "EUR"
      }
    },
    "hasMerchantReturnPolicy": {
      "@type": "MerchantReturnPolicy",
      "merchantReturnDays": 30,
      "returnFees": "https://schema.org/FreeReturn"
    }
  }
}
</script>`,
    productData: {
      name: "MyStore Vintage NC-700 (Shopify Brut)",
      brand: "MyStore Vintage",
      price: "249.00",
      currency: "EUR",
      description: "Fiche produit type Shopify non optimisée : microdonnées JSON-LD absentes, variantes bloquées en JS et balisage WAF bloquant.",
      has_stock: false,
      has_shipping: false,
      has_return: false
    },
    pillars: {
      crawl: { score: 45, max: 100, weight: "30%", status: "Bloqué / WAF Challenge", label: "Crawl & Bots Access" },
      schema: { score: 30, max: 100, weight: "40%", status: "Incomplet (0 Offer)", label: "Schema.org / JSON-LD" },
      tokens: { score: 40, max: 100, weight: "30%", status: "5 840 tokens (Bruit élevé)", label: "Pureté Sémantique" },
      simulator: { score: 35, max: 100, weight: "Simulation", status: "Hallucinations détectées", label: "AI Buyer Simulator (Aperçu)" },
      proto: { score: 0, max: 100, weight: "Protocoles", status: "Inexistant", label: "Protocoles (llms.txt / MCP)" }
    },
    aiView: {
      tokens: "5 840 tokens",
      extractedPrice: "249.00 EUR (Devise non explicite dans JSON-LD)",
      stockStatus: "UNKNOWN (Bouton 'Ajouter au panier' rendu via React client-side)",
      shippingTerms: "MISSING (L'agent IA estime la livraison entre 5€ et 15€)",
      hallucinationRisk: "ÉLEVÉ (45%)",
      botAccess: "GPTBot: BLOCKED (WAF Challenge)"
    }
  },

  ready: {
    domain: "sonus-audio.com/products/nc700-matte-black",
    name: "Sonus Audio NC-700 (Optimisé AgentReady)",
    image: "assets/product_human_view.jpg",
    score: 96,
    status: "ready",
    statusLabel: "Agent Ready (Parfaitement Optimisé)",
    statusBadgeClass: "badge-ready",
    summary: "Fiche produit modèle. Données Schema.org 100% validées, latence de crawl < 210ms, tokens optimisés (780 tokens/fiche), fichier llms.txt certifié et serveur MCP actif pour l'achat autonome.",
    brokenItems: [
      {
        title: "Balisage machine irréprochable",
        impact: "Les bots de ChatGPT, Claude et Perplexity disposent du prix exact, du stock temps réel et des conditions de retour sans hallucination.",
        severity: "info"
      }
    ],
    rawJsonLd: `<script type="application/ld+json">
{
  "@context": "https://schema.org/",
  "@type": "Product",
  "name": "Sonus NC-700 Matte Black",
  "sku": "SONUS-NC700-BLK",
  "offers": {
    "@type": "Offer",
    "price": "249.00",
    "priceCurrency": "EUR",
    "availability": "https://schema.org/InStock",
    "hasMerchantReturnPolicy": {
      "@type": "MerchantReturnPolicy",
      "merchantReturnDays": 30
    }
  }
}
</script>`,
    fixedJsonLd: `<script type="application/ld+json">
{
  "@context": "https://schema.org/",
  "@type": "Product",
  "name": "Sonus NC-700 Matte Black (Certifié AgentReady)",
  "sku": "SONUS-NC700-BLK",
  "gtin13": "3700123456789",
  "brand": { "@type": "Brand", "name": "Sonus" },
  "offers": {
    "@type": "Offer",
    "priceCurrency": "EUR",
    "price": "249.00",
    "availability": "https://schema.org/InStock",
    "shippingDetails": {
      "@type": "OfferShippingDetails",
      "shippingRate": { "@type": "MonetaryAmount", "value": "0.00", "currency": "EUR" }
    },
    "hasMerchantReturnPolicy": {
      "@type": "MerchantReturnPolicy",
      "merchantReturnDays": 30,
      "returnFees": "https://schema.org/FreeReturn"
    }
  }
}
</script>`,
    productData: {
      name: "Sonus NC-700 Matte Black (Certifié)",
      brand: "Sonus Audio Systems",
      price: "249.00",
      currency: "EUR",
      description: "Casque supra-aural premium avec réduction active du bruit adaptative, transducteurs 40mm en titane et 40 heures d'autonomie avec recharge rapide USB-C.",
      has_stock: true,
      has_shipping: true,
      has_return: true
    },
    pillars: {
      crawl: { score: 98, max: 100, weight: "30%", status: "SSR Pré-rendu & Bot-Friendly", label: "Crawl & Bots Access" },
      schema: { score: 96, max: 100, weight: "40%", status: "Complet (Product, Offer, Shipping)", label: "Schema.org / JSON-LD" },
      tokens: { score: 95, max: 100, weight: "30%", status: "780 tokens (0 bruit DOM)", label: "Pureté Sémantique" },
      simulator: { score: 98, max: 100, weight: "Simulation", status: "5/5 Exactitude (0 hallucination)", label: "AI Buyer Simulator (Aperçu)" },
      proto: { score: 94, max: 100, weight: "Protocoles", status: "llms.txt + Serveur MCP Actif", label: "Protocoles (llms.txt / MCP)" }
    },
    aiView: {
      tokens: "780 tokens (-86% de coût)",
      extractedPrice: "249.00 EUR TTC (Garantie prix exact)",
      stockStatus: "IN_STOCK (42 unités disponibles en direct)",
      shippingTerms: "Livraison gratuite 24h France métropolitaine",
      hallucinationRisk: "NUL (0%)",
      botAccess: "GPTBot, ClaudeBot, PerplexityBot: AUTORISÉS"
    }
  },

  friction: {
    domain: "urban-streetwear.co/products/hoodie-heavyweight-grey",
    name: "Urban Streetwear - Hoodie Heavyweight Gris (WooCommerce)",
    image: "https://images.unsplash.com/photo-1556905055-8f358a7a47b2?w=800&auto=format&fit=crop&q=80",
    score: 64,
    status: "friction",
    statusLabel: "Agent Friction (Données partielles)",
    statusBadgeClass: "badge-friction",
    summary: "Le site est accessible mais manque d'attributs critiques : la politique de retour n'est pas structurée et le stock temps réel n'est pas exposé aux robots.",
    brokenItems: [
      {
        title: "Politique de retour et conditions d'échange absentes",
        impact: "Les agents IA indiquent 'conditions inconnues' à l'acheteur, provoquant 35% d'hésitation et d'abandon.",
        severity: "warning"
      },
      {
        title: "Index llms.txt non configuré",
        impact: "Les bots doivent parser manuellement les pages de catalogue au lieu d'ingérer l'index sémantique direct.",
        severity: "info"
      }
    ],
    rawJsonLd: `<script type="application/ld+json">
{
  "@context": "https://schema.org/",
  "@type": "Product",
  "name": "Hoodie Heavyweight Gris",
  "offers": {
    "@type": "Offer",
    "price": "79.00",
    "priceCurrency": "EUR"
    /* hasMerchantReturnPolicy MANQUANT */
    /* shippingDetails MANQUANT */
  }
}
</script>`,
    fixedJsonLd: `<script type="application/ld+json">
{
  "@context": "https://schema.org/",
  "@type": "Product",
  "name": "Hoodie Heavyweight Gris 450 GSM",
  "sku": "URBAN-HD-GRY-01",
  "offers": {
    "@type": "Offer",
    "price": "79.00",
    "priceCurrency": "EUR",
    "availability": "https://schema.org/InStock",
    "shippingDetails": {
      "@type": "OfferShippingDetails",
      "shippingRate": { "@type": "MonetaryAmount", "value": "4.90", "currency": "EUR" }
    },
    "hasMerchantReturnPolicy": {
      "@type": "MerchantReturnPolicy",
      "merchantReturnDays": 14,
      "returnFees": "https://schema.org/FreeReturn"
    }
  }
}
</script>`,
    productData: {
      name: "Hoodie Heavyweight Gris 450 GSM",
      brand: "Urban Streetwear Co",
      price: "79.00",
      currency: "EUR",
      description: "Sweat à capuche molletonné coupe oversize 450 GSM en coton biologique peigné avec finitions bord-côte renforcées.",
      has_stock: true,
      has_shipping: false,
      has_return: false
    },
    pillars: {
      crawl: { score: 75, max: 100, weight: "30%", status: "Robots OK mais latence 1.4s", label: "Crawl & Bots Access" },
      schema: { score: 60, max: 100, weight: "40%", status: "Product OK / Shipping manquant", label: "Schema.org / JSON-LD" },
      tokens: { score: 68, max: 100, weight: "30%", status: "2 450 tokens", label: "Pureté Sémantique" },
      simulator: { score: 62, max: 100, weight: "Simulation", status: "Réponses vagues sur retours", label: "AI Buyer Simulator (Aperçu)" },
      proto: { score: 20, max: 100, weight: "Protocoles", status: "llms.txt partiel, pas de MCP", label: "Protocoles (llms.txt / MCP)" }
    },
    aiView: {
      tokens: "2 450 tokens",
      extractedPrice: "79.00 EUR",
      stockStatus: "En stock (variantes M & L non détaillées)",
      shippingTerms: "Frais de port introuvables dans le DOM machine",
      hallucinationRisk: "MOYEN (22%)",
      botAccess: "Bots IA: AUTORISÉS"
    }
  }
};

/* AI Buyer Simulator Dialogues */
export const SIMULATOR_QUESTIONS = [
  {
    id: "shipping",
    label: "📦 Délais et Frais de Livraison",
    userPrompt: "Je veux acheter le casque Sonus NC-700. Quels sont les frais et délais de livraison pour Lyon ?",
    standardResponse: {
      type: "fail",
      agentStatus: "⚠️ Risque d'hallucination élevé",
      response: "D'après la page, je ne trouve pas d'information explicite sur les frais de port pour Lyon car la section est générée dynamiquement par un script de panier. Les frais sont généralement compris entre 4,90 € et 9,90 €, mais je ne peux pas le garantir avec certitude avant le checkout.",
      verdict: "Recommandation avortée : L'agent IA hésite et renvoie l'utilisateur vers Amazon où la livraison est claire."
    },
    agentReadyResponse: {
      type: "success",
      agentStatus: "✅ Réponse 100% déterministe",
      response: "Le casque Sonus NC-700 est éligible à la livraison express gratuite en 24h à Lyon (France métropolitaine) via Colissimo suivi. La commande passée avant 14h sera expédiée le jour même.",
      verdict: "Recommandation immédiate : L'agent IA valide le panier et propose le paiement sécurisé direct."
    }
  },
  {
    id: "warranty",
    label: "🛡️ Politique de Garantie & Retour",
    userPrompt: "Si le casque ne me convient pas ou est défectueux, quelle est la politique de retour ?",
    standardResponse: {
      type: "fail",
      agentStatus: "⚠️ Information introuvable",
      response: "La fiche produit ne contient pas de données structurées sur les retours (`hasMerchantReturnPolicy` manquant). Le texte du footer mentionne 'conditions générales de vente' mais le robot ne peut pas analyser ce document PDF volumineux.",
      verdict: "Friction d'achat : L'agent avertit l'utilisateur du manque de garantie transparente."
    },
    agentReadyResponse: {
      type: "success",
      agentStatus: "✅ Spécification Schema.org Validée",
      response: "Vous bénéficiez de 30 jours d'essai 'Satisfait ou Remboursé' avec retour gratuit sans frais de réapprovisionnement, plus une garantie constructeur de 2 ans pièces et main d'œuvre.",
      verdict: "Conversion maximale : Confiance absolue confirmée par l'agent IA."
    }
  },
  {
    id: "stock",
    label: "📊 Disponibilité en Stock Temps Réel",
    userPrompt: "Le modèle Noir Mat est-il disponible immédiatement pour un envoi aujourd'hui ?",
    standardResponse: {
      type: "fail",
      agentStatus: "❌ Échec de lecture DOM",
      response: "Le sélecteur de couleur est géré par un script React côté client non exécuté par le bot. Je ne peux pas confirmer si le coloris Noir Mat est disponible ou en rupture.",
      verdict: "Abandon d'achat : Le bot cherche une alternative en stock chez un concurrent."
    },
    agentReadyResponse: {
      type: "success",
      agentStatus: "✅ Flux MCP Temps Réel",
      response: "Oui, le coloris Noir Mat (SKU: NC700-BLK) dispose actuellement de 42 unités en stock prêtes à l'expédition immédiate.",
      verdict: "Succès : Produit sélectionné et validé."
    }
  }
];

/* Auto-Fix Code Templates */
export const CODE_SNIPPETS = {
  llmsTxt: `# LLMS.txt for Sonus Audio
# https://llmstxt.org/ specification v1.0
# Agentic Commerce Index

> Sonus Audio conçoit des casques audio haut de gamme à réduction de bruit active.

## Fiches Produits & Spécifications
- [Sonus NC-700 Matte Black](/products/nc700-black.md): Casque sans fil circum-aural, ANC hybride, Bluetooth 5.3, autonomie 40h, 249.00 EUR TTC.
- [Sonus NC-700 Silver Platinum](/products/nc700-silver.md): Version Argent brossé, 249.00 EUR TTC.

## Conditions Commerciales pour Agents IA
- **Livraison :** Gratuite en 24-48h en France métropolitaine et Union Européenne pour toute commande > 50€.
- **Politique de Retour :** 30 jours d'essai sans frais, étiquette prépayée fournie.
- **Paiement & Checkout :** Compatible Apple Pay, Stripe Agentic API, PayPal.
- **Stock Endpoint MCP :** https://api.sonus-audio.com/mcp/v1/inventory`,

  schemaJson: `<script type="application/ld+json">
{
  "@context": "https://schema.org/",
  "@type": "Product",
  "name": "Sonus NC-700 Matte Black",
  "image": [
    "https://sonus-audio.com/assets/product_human_view.jpg"
  ],
  "description": "Casque supra-aural à réduction active du bruit sans fil, autonomie 40h.",
  "sku": "SONUS-NC700-BLK",
  "gtin13": "3700123456789",
  "brand": {
    "@type": "Brand",
    "name": "Sonus"
  },
  "offers": {
    "@type": "Offer",
    "url": "https://sonus-audio.com/products/nc700-black",
    "priceCurrency": "EUR",
    "price": "249.00",
    "priceValidUntil": "2027-12-31",
    "itemCondition": "https://schema.org/NewCondition",
    "availability": "https://schema.org/InStock",
    "shippingDetails": {
      "@type": "OfferShippingDetails",
      "shippingRate": {
        "@type": "MonetaryAmount",
        "value": "0.00",
        "currency": "EUR"
      },
      "deliveryTime": {
        "@type": "ShippingDeliveryTime",
        "transitTime": {
          "@type": "QuantitativeValue",
          "minValue": 1,
          "maxValue": 2,
          "unitCode": "DAY"
        }
      }
    },
    "hasMerchantReturnPolicy": {
      "@type": "MerchantReturnPolicy",
      "returnPolicyCategory": "https://schema.org/MerchantReturnFiniteReturnWindow",
      "merchantReturnDays": 30,
      "returnFees": "https://schema.org/FreeReturn"
    }
  }
}
</script>`,

  mcpConfig: `{
  "mcpServers": {
    "sonus-store-agent": {
      "command": "npx",
      "args": [
        "-y",
        "@agentready/mcp-server-commerce",
        "--store-id=store_sonus_9823",
        "--api-key=ag_live_sec_8923bca0129"
      ],
      "env": {
        "AGENTREADY_REGION": "eu-west-1",
        "AUTO_RESERVE_INVENTORY": "true"
      },
      "capabilities": [
        "query_product_stock",
        "validate_discount_code",
        "generate_cart_checkout_token"
      ]
    }
  }
}`
};
