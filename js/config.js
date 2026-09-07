/* ==========================================================================
   AGENTREADY - Configuration monétisation
   Éditez ce fichier (et lui seul) pour brancher vos canaux de conversion.
   Aucun changement de code dans app.js / index.html n'est nécessaire.
   ========================================================================== */

// Lien de réservation de démo / call de vente (Calendly, Cal.com, TidyCal…).
// Ex: "https://calendly.com/belhaj/audit-agentready"
// Tant qu'il est vide, le CTA "Contacter l'équipe Agence" retombe sur un email.
export const BOOKING_URL = '';

// Lien de paiement Stripe (Payment Link) pour l'offre Pro self-serve.
// Laissez vide tant que le modèle reste 100% concierge (high-ticket).
// Si vide, le CTA "Commencer l'essai" retombe sur BOOKING_URL puis sur l'email.
export const CHECKOUT_URL = '';

// Email de contact de secours (utilisé uniquement quand les URLs sont vides).
export const CONTACT_EMAIL = 'contact@agentready.io';
