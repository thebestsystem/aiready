"""
==========================================================================
AGENTREADY - Autorepondeur / Séquence de Nurture (9 emails)
==========================================================================
Envoie une séquence de 9 emails au lead après capture du rapport PDF.
- Email 0 (J+0) : envoyé immédiatement lors de la capture (si consentement).
- Emails 1..8 (J+1..J+8) : envoyés par le cron via /api/process-email-sequence.

Persistance : table `email_sequence` (PostgreSQL, si DATABASE_URL configurée).
Envoi : Resend (transactionnel), même infra que lead_sink.
==========================================================================
"""

import os
import logging
from datetime import datetime, timezone
from typing import Dict, Optional

import httpx

logger = logging.getLogger("agentready.email_sequence")

RESEND_API_URL = "https://api.resend.com/emails"
RESEND_DEFAULT_FROM = "AgentReady <audit@8dev.net>"
BASE_URL = os.getenv("BASE_URL", "https://aiready-production-a6c0.up.railway.app").rstrip("/")
TRIAL_URL = os.getenv("STRIPE_PRO_LINK", "https://buy.stripe.com/7sY8wQb4xfdgfYY19hco003")

# Détection psycopg (v3 ou v2)
PSYCOPG_AVAILABLE = False
try:
    import psycopg
    PSYCOPG_AVAILABLE = True
except ImportError:
    try:
        import psycopg2 as psycopg
        PSYCOPG_AVAILABLE = True
    except ImportError:
        pass

_FOOTER = (
    "<p style='color:#64748b;font-size:12px;margin-top:24px;'>"
    "Vous recevez cet email car vous avez demandé un rapport d'audit AgentReady. "
    "Désinscription : répondez simplement « STOP » à cet email."
    "</p>"
)

# ==========================================================================
# SÉQUENCE DES 9 EMAILS — placeholders : {domain} {score} {status} {name} {site} {trial}
# ==========================================================================
SEQUENCE = [
    {
        "subject": "Votre rapport d'audit AgentReady est prêt 📊",
        "body": (
            "<p>Bonjour,</p>"
            "<p>Votre audit de <b>{domain}</b> est prêt.</p>"
            "<p><b>Score global : {score}/100</b> — <b>{status}</b>.</p>"
            "<p>Le rapport détaille les 5 piliers (Crawl, Schema, Tokens, Simulation, Protocoles) "
            "et les failles exactes qui bloquent les agents d'achat IA (ChatGPT, Gemini, Claude).</p>"
            "<p><a href='{site}' style='color:#06b6d4;'>Voir les corrections en 1 clic →</a></p>"
            + _FOOTER
        ),
    },
    {
        "subject": "Ce que votre score de {score}/100 signifie vraiment",
        "body": (
            "<p>Bonjour,</p>"
            "<p>Votre score de <b>{score}/100</b> n'est pas un jugement esthétique : c'est une mesure de "
            "<b>certitude transactionnelle</b>. Un agent IA ne recommande un produit que s'il peut confirmer "
            "prix, stock, livraison et retour sans risque d'hallucination.</p>"
            "<p>Les 5 piliers pondérés : Crawl (20%), Schema.org (25%), Tokens (20%), Simulation (20%), Protocoles (15%).</p>"
            "<p><a href='{site}#pillars' style='color:#06b6d4;'>Décoder mon score pilier par pilier →</a></p>"
            + _FOOTER
        ),
    },
    {
        "subject": "Les failles qui coûtent des ventes à {domain}",
        "body": (
            "<p>Bonjour,</p>"
            "<p>Voici ce que l'audit a détecté sur <b>{domain}</b> :</p>"
            "<ul>"
            "<li><b>Schema.org incomplet ou absent</b> — l'IA ne peut pas certifier le prix ni le stock.</li>"
            "<li><b>Risque d'hallucination</b> — frais de port ou politique de retour illisibles.</li>"
            "<li><b>Protocoles agentiques manquants</b> — pas de llms.txt ni de serveur MCP.</li>"
            "</ul>"
            "<p>Chaque faille = un client perdu au profit d'un concurrent mieux structuré.</p>"
            "<p><a href='{trial}' style='color:#06b6d4;'>Corriger ça avec l'essai gratuit →</a></p>"
            + _FOOTER
        ),
    },
    {
        "subject": "Réparez {domain} en 1 clic",
        "body": (
            "<p>Bonjour,</p>"
            "<p>AgentReady ne fait pas que diagnostiquer : il <b>génère les correctifs</b> prêts à déployer.</p>"
            "<ul>"
            "<li>JSON-LD Schema.org enrichi (prix, devise, stock, retour).</li>"
            "<li>Fichier <code>llms.txt</code> standard.</li>"
            "<li>Serveur MCP dédié pour connecter votre boutique aux agents IA.</li>"
            "</ul>"
            "<p>Copiez, collez, c'est corrigé. Compatible Shopify, WooCommerce, Magento, Webflow.</p>"
            "<p><a href='{site}#autofix' style='color:#06b6d4;'>Voir le générateur auto-fix →</a></p>"
            + _FOOTER
        ),
    },
    {
        "subject": "Voici ce que ChatGPT répond sur {domain}",
        "body": (
            "<p>Bonjour,</p>"
            "<p>Un acheteur pose « Livraison gratuite ? » à un agent IA. La réponse dépend de la structure de votre fiche :</p>"
            "<ul>"
            "<li><b>Sans AgentReady :</b> « je ne peux pas confirmer » → panier abandonné.</li>"
            "<li><b>Avec AgentReady :</b> « livraison gratuite, en stock » → achat validé.</li>"
            "</ul>"
            "<p>C'est l'AI Buyer Simulator : il teste réellement ce que répondent ChatGPT et Gemini sur votre boutique.</p>"
            "<p><a href='{site}#simulator' style='color:#06b6d4;'>Tester le simulateur →</a></p>"
            + _FOOTER
        ),
    },
    {
        "subject": "Vos concurrents sont-ils prêts pour l'AI search ?",
        "body": (
            "<p>Bonjour,</p>"
            "<p>Le trafic issu des moteurs IA a bondi de <b>+805%</b> en glissement annuel, avec un taux de conversion "
            "<b>2,5x à 4x supérieur</b> au trafic de recherche classique (McKinsey, Bain, Morgan Stanley).</p>"
            "<p>La question n'est plus « est-ce que ça arrive ? » mais « qui capte ce trafic en premier ? » "
            "Chaque semaine sans optimisation = des recommandations qui partent chez un concurrent.</p>"
            "<p><a href='{site}#pricing' style='color:#06b6d4;'>Prendre de l'avance maintenant →</a></p>"
            + _FOOTER
        ),
    },
    {
        "subject": "Tout ce que Pro Merchant débloque pour {domain}",
        "body": (
            "<p>Bonjour,</p>"
            "<p>Le plan Pro Merchant (49€/mois) débloque :</p>"
            "<ul>"
            "<li><b>250 fiches produit</b> monitorées / mois.</li>"
            "<li><b>AI Buyer Simulator complet</b> (50 requêtes Gemini).</li>"
            "<li>Export illimité de <code>llms.txt</code> & JSON-LD enrichi.</li>"
            "<li><b>Serveur MCP Cloud dédié</b> hébergé.</li>"
            "<li>Alertes d'intégrité de thème par email.</li>"
            "</ul>"
            "<p><a href='{trial}' style='color:#06b6d4;'>Commencer l'essai de 14 jours →</a></p>"
            + _FOOTER
        ),
    },
    {
        "subject": "Votre essai de 14 jours vous attend",
        "body": (
            "<p>Bonjour,</p>"
            "<p>Vous avez vu le diagnostic sur <b>{domain}</b>. Il est temps de le corriger.</p>"
            "<p>L'essai de 14 jours est <b>gratuit et sans engagement</b> : scanner 250 fiches, "
            "générer vos correctifs, et voir la différence sur le simulateur IA.</p>"
            "<p>Aucun risque : résiliable en un clic.</p>"
            "<p><a href='{trial}' style='color:#06b6d4;font-weight:bold;'>Démarrer mon essai gratuit →</a></p>"
            + _FOOTER
        ),
    },
    {
        "subject": "Dernier rappel avant de fermer votre dossier",
        "body": (
            "<p>Bonjour,</p>"
            "<p>Dernier message — je ferme le dossier {domain} après celui-ci pour ne pas vous submerger.</p>"
            "<p>Le rapport est toujours là, et l'essai de 14 jours reste ouvert. "
            "Passé ce point, vos concurrents continueront de capter le trafic IA pendant que vous tergiversez.</p>"
            "<p><a href='{trial}' style='color:#06b6d4;font-weight:bold;'>Activer mon essai (dernière chance) →</a></p>"
            + _FOOTER
        ),
    },
]


# ==========================================================================
# HELPERS DB
# ==========================================================================
def _db_conn() -> Optional[str]:
    url = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_URL")
    if not url or not PSYCOPG_AVAILABLE:
        return None
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


def _init_table(conn_str: str) -> bool:
    try:
        with psycopg.connect(conn_str) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS email_sequence (
                        email VARCHAR(255) PRIMARY KEY,
                        domain VARCHAR(255),
                        name VARCHAR(255),
                        score INTEGER,
                        status VARCHAR(100),
                        last_index INTEGER DEFAULT 0,
                        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
                conn.commit()
        return True
    except Exception as e:
        logger.warning(f"Impossible d'initialiser la table email_sequence : {e}")
        return False


# ==========================================================================
# ENVOI RESEND
# ==========================================================================
def send_email(api_key: str, from_addr: str, to_email: str, subject: str, html_body: str) -> bool:
    """Envoie un email transactionnel via Resend."""
    if not api_key or not to_email:
        return False
    payload = {
        "from": from_addr,
        "to": [to_email],
        "subject": subject,
        "html": html_body,
    }
    try:
        resp = httpx.post(
            RESEND_API_URL,
            json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=8.0,
        )
        return resp.status_code in (200, 201, 202)
    except Exception as e:
        logger.warning(f"Échec envoi Resend : {e}")
        return False


def _format_body(index: int, lead: Dict) -> str:
    item = SEQUENCE[index]
    vals = {
        "domain": str(lead.get("domain") or "votre boutique"),
        "score": str(lead.get("score") or "--"),
        "status": str(lead.get("status") or "Audit"),
        "name": str(lead.get("name") or "Boutique"),
        "site": BASE_URL,
        "trial": TRIAL_URL,
    }
    return item["body"].format(**vals)


def _format_subject(index: int, lead: Dict) -> str:
    item = SEQUENCE[index]
    vals = {
        "domain": str(lead.get("domain") or "votre boutique"),
        "score": str(lead.get("score") or "--"),
        "status": str(lead.get("status") or "Audit"),
        "name": str(lead.get("name") or "Boutique"),
    }
    return item["subject"].format(**vals)


# ==========================================================================
# POINTS D'ENTRÉE
# ==========================================================================
def register_subscriber(email: str, domain: str, name: str, score: int, status: str) -> bool:
    """Upsert le lead dans email_sequence (s'il a consenti). Renvoie True si nouveau."""
    conn_str = _db_conn()
    if not conn_str:
        return False
    try:
        _init_table(conn_str)
        with psycopg.connect(conn_str) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO email_sequence (email, domain, name, score, status)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (email) DO NOTHING
                    """,
                    (email.strip(), domain.strip(), name.strip(), score, status.strip()),
                )
                conn.commit()
                return cur.rowcount > 0
    except Exception as e:
        logger.error(f"Erreur register_subscriber : {e}")
        return False


def send_welcome(email: str, domain: str, name: str, score: int, status: str) -> bool:
    """Envoie l'email J+0 immédiatement au lead."""
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        return False
    from_addr = os.getenv("RESEND_FROM") or RESEND_DEFAULT_FROM
    lead = {"domain": domain, "name": name, "score": score, "status": status}
    return send_email(api_key, from_addr, email, _format_subject(0, lead), _format_body(0, lead))


def process_sequence() -> Dict:
    """Envoie les emails différés dus (J+1..J+8). Appelé par le cron."""
    conn_str = _db_conn()
    if not conn_str:
        return {"ok": False, "reason": "no_database", "sent": 0}

    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        return {"ok": False, "reason": "no_resend_key", "sent": 0}
    from_addr = os.getenv("RESEND_FROM") or RESEND_DEFAULT_FROM

    try:
        _init_table(conn_str)
        now = datetime.now(timezone.utc)
        sent = 0
        with psycopg.connect(conn_str) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT email, domain, name, score, status, last_index, created_at FROM email_sequence"
                )
                rows = cur.fetchall()
                for email, domain, name, score, status, last_index, created_at in rows:
                    created = created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
                    age_days = (now - created).days
                    due = min(age_days, len(SEQUENCE) - 1)
                    for i in range(last_index + 1, due + 1):
                        if i < 1:  # l'email 0 est envoyé par send_welcome
                            continue
                        lead = {"domain": domain, "name": name, "score": score, "status": status}
                        ok = send_email(
                            api_key, from_addr, email,
                            _format_subject(i, lead), _format_body(i, lead),
                        )
                        if ok:
                            sent += 1
                            cur.execute(
                                "UPDATE email_sequence SET last_index = %s WHERE email = %s",
                                (i, email),
                            )
                            conn.commit()
        return {"ok": True, "sent": sent}
    except Exception as e:
        logger.error(f"Erreur process_sequence : {e}")
        return {"ok": False, "error": str(e), "sent": 0}


# ==========================================================================
# EMAIL DE BIENVENUE POST-PAIEMENT (onboarding du nouveau client payant)
# ==========================================================================
def send_payment_welcome(email: str, name: str = "") -> bool:
    """Envoie l'email de bienvenue immédiatement après un paiement réussi."""
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        return False
    from_addr = os.getenv("RESEND_FROM") or RESEND_DEFAULT_FROM
    name = (name or "").strip() or "Client"
    subject = "Bienvenue chez AgentReady — vos 3 prochaines étapes 🚀"
    body = (
        f"<p>Bonjour {name},</p>"
        f"<p>Bienvenue ! Votre abonnement AgentReady est actif. Voici vos 3 prochaines étapes :</p>"
        f"<ol>"
        f"<li><b>Lancez votre premier audit</b> — collez l'URL de votre boutique sur "
        f"<a href='{BASE_URL}' style='color:#06b6d4;'>la page d'accueil</a> et scannez.</li>"
        f"<li><b>Retrouvez vos scans</b> — tous vos audits sont regroupés dans votre "
        f"<a href='{BASE_URL}/dashboard' style='color:#06b6d4;'>tableau de bord</a>.</li>"
        f"<li><b>Gérez votre abonnement</b> — carte, factures, annulation : "
        f"<a href='{BASE_URL}/espace-client' style='color:#06b6d4;'>votre espace client</a>.</li>"
        f"</ol>"
        f"<p>À très vite,<br>L'équipe AgentReady</p>"
        f"<p style='color:#64748b;font-size:12px;margin-top:24px;'>"
        f"Vous recevez cet email car vous êtes client AgentReady. "
        f"Gérer votre abonnement : <a href='{BASE_URL}/espace-client' style='color:#06b6d4;'>espace client</a>."
        f"</p>"
    )
    return send_email(api_key, from_addr, email, subject, body)
