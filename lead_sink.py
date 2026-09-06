"""
==========================================================================
AGENTREADY - Service Résilient de Capture de Leads (Lead Sink)
==========================================================================
Persistance PostgreSQL + Notification temps réel Slack/Discord + Backup CSV local.
Garantie zéro-perte : aucun échec distant ne bloque l'expérience utilisateur.
"""

import os
import csv
import html
import logging
from datetime import datetime
from typing import Optional, Dict, Any

import httpx

logger = logging.getLogger("agentready.lead_sink")

# Détection des drivers PostgreSQL (psycopg v3 ou psycopg2)
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

LEADS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leads.csv")
_table_initialized = False


def _init_db(conn_str: str) -> bool:
    """Initialise la table leads et ses index dans PostgreSQL si non existants."""
    global _table_initialized
    if not PSYCOPG_AVAILABLE or not conn_str:
        return False
    if _table_initialized:
        return True

    try:
        # Normalisation connection string si nécessaire (ex: postgres:// -> postgresql://)
        fixed_conn_str = conn_str
        if fixed_conn_str.startswith("postgres://"):
            fixed_conn_str = fixed_conn_str.replace("postgres://", "postgresql://", 1)

        with psycopg.connect(fixed_conn_str) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS leads (
                        id SERIAL PRIMARY KEY,
                        email VARCHAR(255) NOT NULL,
                        domain VARCHAR(255) NOT NULL,
                        product_name VARCHAR(255),
                        score INTEGER,
                        status VARCHAR(100),
                        hallucination_risk VARCHAR(50),
                        source VARCHAR(50) DEFAULT 'scanner',
                        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads(created_at);
                    CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email);
                """)
                conn.commit()
        _table_initialized = True
        return True
    except Exception as e:
        logger.warning(f"Impossible d'initialiser la table leads Postgres : {e}")
        return False


def _save_to_postgres(
    conn_str: str,
    email: str,
    domain: str,
    name: str,
    score: int,
    status: str,
    risk: str,
    source: str
) -> bool:
    """Insère un lead de manière transactionnelle dans PostgreSQL."""
    if not PSYCOPG_AVAILABLE or not conn_str:
        return False

    try:
        _init_db(conn_str)
        fixed_conn_str = conn_str
        if fixed_conn_str.startswith("postgres://"):
            fixed_conn_str = fixed_conn_str.replace("postgres://", "postgresql://", 1)

        with psycopg.connect(fixed_conn_str) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO leads (email, domain, product_name, score, status, hallucination_risk, source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    email.strip(),
                    domain.strip(),
                    name.strip(),
                    score,
                    status.strip(),
                    risk.strip(),
                    source.strip()
                ))
                conn.commit()
        return True
    except Exception as e:
        logger.error(f"Erreur d'insertion lead PostgreSQL : {e}")
        return False


def _send_slack_alert(
    webhook_url: str,
    email: str,
    domain: str,
    name: str,
    score: int,
    status: str,
    risk: str,
    source: str
) -> bool:
    """Envoie une notification push instantanée sur Slack ou Discord."""
    if not webhook_url or not webhook_url.strip():
        return False

    payload = {
        "text": f"🚨 *Nouveau Lead E-commerce capturé !*\n"
                f"• *Email :* `{email.strip()}`\n"
                f"• *Boutique :* {domain.strip()}\n"
                f"• *Produit :* {name.strip()}\n"
                f"• *Score Global :* `{score}/100` ({status.strip()})\n"
                f"• *Risque Hallucination :* {risk.strip()}\n"
                f"• *Origine :* {source.strip()}\n"
                f"• *Date :* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    }

    try:
        resp = httpx.post(webhook_url.strip(), json=payload, timeout=3.0)
        return resp.status_code in [200, 204]
    except Exception as e:
        logger.warning(f"Échec webhook Slack : {e}")
        return False


RESEND_API_URL = "https://api.resend.com/emails"
RESEND_DEFAULT_FROM = "AgentReady <audit@8dev.net>"


def _send_resend_email(
    api_key: str,
    from_addr: str,
    to_addr: str,
    email: str,
    domain: str,
    name: str,
    score: int,
    status: str,
    risk: str,
    source: str
) -> bool:
    """Envoie une alerte email temps réel aux fondateurs via Resend (transactionnel)."""
    if not api_key or not from_addr or not to_addr:
        return False

    payload = {
        "from": from_addr,
        "to": [to_addr],
        "subject": f"🚀 Nouveau lead AgentReady : {domain} ({score}/100)",
        "html": (
            "<h3>🚨 Nouveau lead e-commerce capturé</h3>"
            "<ul>"
            f"<li><b>Email :</b> {html.escape(email)}</li>"
            f"<li><b>Boutique :</b> {html.escape(domain)}</li>"
            f"<li><b>Produit :</b> {html.escape(name)}</li>"
            f"<li><b>Score :</b> {score}/100 ({html.escape(status)})</li>"
            f"<li><b>Risque hallucination :</b> {html.escape(risk)}</li>"
            f"<li><b>Origine :</b> {html.escape(source)}</li>"
            f"<li><b>Date :</b> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</li>"
            "</ul>"
        ),
    }

    try:
        resp = httpx.post(
            RESEND_API_URL,
            json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=5.0,
        )
        return resp.status_code in (200, 201, 202)
    except Exception as e:
        logger.warning(f"Échec email Resend : {e}")
        return False


def _save_to_csv(
    email: str,
    domain: str,
    name: str,
    score: int,
    status: str,
    risk: str,
    source: str = "scanner"
) -> bool:
    """Garantie zéro-perte locale : écriture dans leads.csv."""
    file_exists = os.path.exists(LEADS_FILE)
    try:
        with open(LEADS_FILE, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Date", "Email", "URL_Boutique", "Nom_Produit", "Score", "Statut", "Risque_Hallucination", "Source"])
            writer.writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                email.strip(),
                domain.strip(),
                name.strip(),
                score,
                status.strip(),
                risk.strip(),
                source.strip()
            ])
        return True
    except Exception as e:
        logger.critical(f"Erreur critique backup CSV : {e}")
        return False


def dispatch_lead(
    email: str,
    domain: str,
    name: str = "Boutique E-commerce",
    score: int = 50,
    status: str = "Agent Friction",
    risk: str = "MOYEN",
    source: str = "scanner"
) -> Dict[str, bool]:
    """
    Point d'entrée unique de sortie de lead.
    Exécute en parallèle/cascade :
    1. Backup local CSV (toujours garanti)
    2. Insertion PostgreSQL transactionnelle (si DATABASE_URL configurée)
    3. Alerte Slack temps réel (si SLACK_WEBHOOK_URL configurée)
    4. Email de notification fondateur Resend (si RESEND_API_KEY + RESEND_NOTIFY_TO configurés)
    """
    csv_ok = _save_to_csv(email, domain, name, score, status, risk, source)

    db_url = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_URL")
    db_ok = _save_to_postgres(db_url, email, domain, name, score, status, risk, source) if db_url else False

    slack_url = os.getenv("SLACK_WEBHOOK_URL")
    slack_ok = _send_slack_alert(slack_url, email, domain, name, score, status, risk, source) if slack_url else False

    resend_key = os.getenv("RESEND_API_KEY")
    resend_from = os.getenv("RESEND_FROM") or RESEND_DEFAULT_FROM
    resend_to = os.getenv("RESEND_NOTIFY_TO")
    resend_ok = (
        _send_resend_email(resend_key, resend_from, resend_to, email, domain, name, score, status, risk, source)
        if resend_key and resend_to
        else False
    )

    return {
        "csv_saved": csv_ok,
        "db_saved": db_ok,
        "slack_sent": slack_ok,
        "resend_sent": resend_ok
    }
