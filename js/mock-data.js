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
    summary: "Cette boutique bloque ChatGPT via un pare-feu et n'expose ni prix ni stock de façon lisible. Résultat : l'IA invente jusqu'à 40 % de ses réponses.",
    brokenItems: [
      {
        title: "ChatGPT est bloqué à l'entrée de la boutique",
        impact: "Les robots de ChatGPT et Perplexity reçoivent un captcha et ne peuvent pas lire vos produits — la vente part ailleurs.",
        severity: "critical"
      },
      {
        title: "Prix et stock illisibles pour l'IA",
        impact: "Aucun prix ni stock certifié : ChatGPT refuse de recommander le produit.",
        severity: "critical"
      },
      {
        title: "Fiche trop « bruitée » pour l'IA",
        impact: "Trop de code parasite : l'IA se fatigue et peut abandonner la fiche.",
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
      crawl: { score: 45, max: 100, weight: "25%", status: "Bloqué par un pare-feu", label: "ChatGPT peut-il vous lire ?" },
      schema: { score: 30, max: 100, weight: "30%", status: "Incomplet", label: "Vos données produit (prix, stock)" },
      tokens: { score: 40, max: 100, weight: "20%", status: "Très bruité", label: "Clarté de vos fiches" },
      simulator: { score: 35, max: 100, weight: "25%", status: "Hallucinations détectées", label: "Complétude de l'offre" },
      proto: { score: 10, max: 100, weight: "Bonus", status: "Non connecté", label: "Protocoles (bonus, non noté)" }
    },
    aiView: {
      tokens: "5 840 tokens de lecture",
      extractedPrice: "249.00 EUR (devise à confirmer)",
      stockStatus: "Inconnu (non précisé dans le code)",
      shippingTerms: "Non précisés (l'IA estime entre 5€ et 15€)",
      hallucinationRisk: "ÉLEVÉ",
      botAccess: "Bloqués (pare-feu)"
    }
  },

  ready: {
    domain: "sonus-audio.store/products/nc-700-black",
    name: "Sonus NC-700 Matte Black (Shopify)",
    image: "assets/product_human_view.jpg",
    score: 96,
    status: "ready",
    statusLabel: "Agent Ready (Parfaitement Optimisé)",
    statusBadgeClass: "badge-ready",
    summary: "Fiche produit modèle : prix, stock et conditions parfaitement lisibles par ChatGPT. Il recommande le produit et valide le panier sans hésitation.",
    brokenItems: [
      {
        title: "Boutique prête pour l'achat IA ✓",
        impact: "ChatGPT dispose du prix exact, du stock et des conditions de retour — sans rien inventer.",
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
      crawl: { score: 98, max: 100, weight: "25%", status: "Accès libre pour ChatGPT", label: "ChatGPT peut-il vous lire ?" },
      schema: { score: 96, max: 100, weight: "30%", status: "Complet", label: "Vos données produit (prix, stock)" },
      tokens: { score: 95, max: 100, weight: "20%", status: "Très clair", label: "Clarté de vos fiches" },
      simulator: { score: 98, max: 100, weight: "25%", status: "5/5 points vérifiés", label: "Complétude de l'offre" },
      proto: { score: 94, max: 100, weight: "Bonus", status: "Connecté", label: "Protocoles (bonus, non noté)" }
    },
    aiView: {
      tokens: "780 tokens de lecture",
      extractedPrice: "249.00 EUR TTC (Garantie prix exact)",
      stockStatus: "En stock (42 unités disponibles en direct)",
      shippingTerms: "Livraison gratuite 24h France métropolitaine",
      hallucinationRisk: "NUL",
      botAccess: "Autorisés"
    }
  },

  friction: {
    domain: "urban-streetwear.co/products/hoodie-heavyweight-grey",
    name: "Urban Streetwear - Hoodie Heavyweight Gris (WooCommerce)",
    image: "https://images.unsplash.com/photo-1556905055-8f358a7a47b2?w=800&auto=format&fit=crop&q=80",
    score: 61,
    status: "friction",
    statusLabel: "Agent Friction (Données partielles)",
    statusBadgeClass: "badge-friction",
    summary: "ChatGPT accède à votre site, mais il lui manque des infos clés : la politique de retour et le stock ne sont pas lisibles.",
    brokenItems: [
      {
        title: "Politique de retour et échanges pas assez clairs",
        impact: "ChatGPT répond « conditions inconnues » à l'acheteur, qui hésite et abandonne.",
        severity: "warning"
      },
      {
        title: "Pas de « carte d'identité » pour les moteurs IA",
        impact: "ChatGPT doit explorer vos pages une par une au lieu d'utiliser votre fiche de référence.",
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
      has_return: false,
      image: "https://images.unsplash.com/photo-1556905055-8f358a7a47b2?w=800&auto=format&fit=crop&q=80"
    },
    pillars: {
      crawl: { score: 75, max: 100, weight: "25%", status: "Accès OK", label: "ChatGPT peut-il vous lire ?" },
      schema: { score: 60, max: 100, weight: "30%", status: "Incomplet (livraison manquante)", label: "Vos données produit (prix, stock)" },
      tokens: { score: 68, max: 100, weight: "20%", status: "Assez clair", label: "Clarté de vos fiches" },
      simulator: { score: 62, max: 100, weight: "25%", status: "Réponses vagues sur retours", label: "Complétude de l'offre" },
      proto: { score: 35, max: 100, weight: "Bonus", status: "Partiellement connecté", label: "Protocoles (bonus, non noté)" }
    },
    aiView: {
      tokens: "2 450 tokens de lecture",
      extractedPrice: "79.00 EUR",
      stockStatus: "En stock (variantes M & L non détaillées)",
      shippingTerms: "Frais de port introuvables",
      hallucinationRisk: "MOYEN",
      botAccess: "Autorisés"
    }
  }
};

/* Complétude de l'offre Dialogues */
export const SIMULATOR_QUESTIONS = [
  {
    id: "shipping",
    label: "📦 Délais et Frais de Livraison",
    userPrompt: "Je veux acheter le casque Sonus NC-700. Quels sont les frais et délais de livraison pour Lyon ?",
    standardResponse: {
      type: "fail",
      agentStatus: "⚠️ Risque d'hallucination élevé",
      response: "D'après la page, je ne trouve pas d'information explicite sur les frais de port pour Lyon car la boutique n'affiche pas clairement ses frais de port sur la fiche. Les frais sont généralement compris entre 4,90 € et 9,90 €, mais je ne peux pas le garantir avec certitude avant le checkout.",
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
      response: "La fiche produit n'indique pas clairement sa politique de retour. Le texte du footer mentionne 'conditions générales de vente' mais le robot ne peut pas analyser ce document PDF volumineux.",
      verdict: "Friction d'achat : L'agent avertit l'utilisateur du manque de garantie transparente."
    },
    agentReadyResponse: {
      type: "success",
      agentStatus: "✅ Données produit certifiées",
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
      agentStatus: "❌ Stock illisible",
      response: "La boutique affiche le stock via un menu que le robot ne peut pas lire. Je ne peux pas confirmer si le coloris Noir Mat est disponible ou en rupture.",
      verdict: "Abandon d'achat : Le bot cherche une alternative en stock chez un concurrent."
    },
    agentReadyResponse: {
      type: "success",
      agentStatus: "✅ Stock en temps réel",
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
- **Flux produit :** Flux de données structurées mis à jour en temps réel.`,

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
</script>`
};
