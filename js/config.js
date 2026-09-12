/* ==========================================================================
   AGENTREADY - Configuration monétisation
   Éditez ce fichier (et lui seul) pour brancher vos canaux de conversion.
   Aucun changement de code dans app.js / index.html n'est nécessaire.
   ========================================================================== */

// Lien de réservation de démo / call de vente (Calendly, Cal.com, TidyCal…).
// Ex: "https://calendly.com/belhaj/audit-agentready"
// Tant qu'il est vide, le CTA "Contacter l'équipe Agence" retombe sur un email.
export const BOOKING_URL = '';

// Lien de paiement Stripe (Payment Link) LIVE — 49€/mois, 14 jours d'essai.
export const CHECKOUT_URL = 'https://buy.stripe.com/7sY8wQb4xfdgfYY19hco003';

// Lien de paiement Stripe (Payment Link) LIVE — offre Agence 199€/mois, 14 jours d'essai.
export const AGENCY_CHECKOUT_URL = 'https://buy.stripe.com/4gM8wQa0te9cdQQ3hpco004';

// Lien de paiement Stripe (Payment Link) LIVE — Pro Merchant ANNUEL (39€/mois facturé annuellement = 468€/an), 14 jours d'essai.
export const CHECKOUT_URL_ANNUAL = 'https://buy.stripe.com/eVqfZi4G9e9cfYY05dco005';

// Lien de paiement Stripe (Payment Link) LIVE — offre Agence ANNUEL (159€/mois facturé annuellement = 1908€/an), 14 jours d'essai.
export const AGENCY_CHECKOUT_URL_ANNUAL = 'https://buy.stripe.com/8x2cN6egJ3uyaEE2dlco006';

// Email de contact de secours (utilisé uniquement quand les URLs sont vides).
export const CONTACT_EMAIL = 'contact@agentready.io';
