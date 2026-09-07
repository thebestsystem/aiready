"""
==========================================================================
PDF generator module (extracté du monolithe server.py — refactor P1)
==========================================================================
Rendus ReportLab des "Rapports d'Audit AgentReady" (white-label).

Déplacé de `server.py` (ex `generate_pdf_report`) pour alléger le fichier
moteur et permettre un test ciblé, sans casser la signature.
"""

import io
from datetime import datetime
from typing import Dict, Any, Optional

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, Preformatted,
    )
    REPORTLAB_AVAILABLE = True
except ImportError:  # pragma: no cover - dépendance optionnelle hors prod
    REPORTLAB_AVAILABLE = False


from xml.sax.saxutils import escape as _sax_escape


def _escape_xml(val: Any) -> str:
    """Échappe le texte dynamique pour éviter les erreurs de parsing XML dans ReportLab Paragraph."""
    if val is None:
        return ""
    return _sax_escape(str(val))


def generate_pdf_report(audit_data: Dict[str, Any], email: Optional[str] = None) -> bytes:
    """Génère le PDF d'audit (bytes). Lève RuntimeError si ReportLab absent."""
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("ReportLab n'est pas installé sur le serveur.")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    story = []

    # Custom Palette
    c_cyan = colors.HexColor('#06b6d4')
    c_emerald = colors.HexColor('#10b981')
    c_rose = colors.HexColor('#f43f5e')
    c_amber = colors.HexColor('#f59e0b')
    c_text_muted = colors.HexColor('#64748b')

    brand_style = ParagraphStyle(
        'BrandStyle',
        parent=styles['Normal'],
        fontSize=10,
        leading=13,
        textColor=c_cyan,
        fontName='Helvetica-Bold'
    )
    title_style = ParagraphStyle(
        'MainTitle',
        parent=styles['Heading1'],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#0f172a'),
        fontName='Helvetica-Bold'
    )
    section_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontSize=13,
        leading=16,
        textColor=colors.HexColor('#0f172a'),
        fontName='Helvetica-Bold'
    )
    normal_style = ParagraphStyle(
        'NormalText',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#334155')
    )
    code_style = ParagraphStyle(
        'CodeSnippet',
        parent=styles['Code'],
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor('#1e293b'),
        fontName='Courier'
    )

    # 1. Header Banner
    date_str = datetime.now().strftime("%d/%m/%Y à %H:%M")
    header_data = [
        [
            Paragraph("<b>AgentReady</b> • Rapport d'Audit White-Label 2026", brand_style),
            Paragraph(f"Date d'analyse : <b>{date_str}</b>", normal_style)
        ]
    ]
    t_header = Table(header_data, colWidths=[360, 180])
    t_header.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))
    story.append(t_header)
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1.5, color=c_cyan, spaceBefore=0, spaceAfter=15))

    # 2. Executive Summary Block
    name = audit_data.get("name") or "Boutique E-commerce"
    domain = audit_data.get("domain") or "https://example.com"
    score = audit_data.get("score", 50)
    status_label = audit_data.get("statusLabel") or ("Agent Ready" if score >= 80 else ("Agent Friction" if score >= 50 else "Agent Blind"))
    summary_text = audit_data.get("summary") or "Évaluation de la préparation de la boutique pour les agents d'achat IA."

    score_color = c_emerald if score >= 80 else (c_amber if score >= 50 else c_rose)
    score_color_hex = f"#{score_color.hexval()[2:]}"

    safe_name = _escape_xml(name)
    safe_domain = _escape_xml(domain)
    safe_status_label = _escape_xml(status_label)
    safe_summary = _escape_xml(summary_text)
    safe_email = _escape_xml(email) if email else "Confidentiel"

    story.append(Paragraph(f"Audit Technique : {safe_name}", title_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"URL cible : <u>{safe_domain}</u>", normal_style))
    story.append(Spacer(1, 12))

    summary_box_data = [
        [
            Paragraph(f"<font size=28 color='{score_color_hex}'><b>{score}</b></font><font size=14 color='#64748b'>/100</font><br/><br/><b>Statut :</b> {safe_status_label}", normal_style),
            Paragraph(f"<b>Synthèse de l'Audit :</b><br/>{safe_summary}<br/><br/><i>Client destinataire : {safe_email}</i>", normal_style)
        ]
    ]
    t_summary = Table(summary_box_data, colWidths=[160, 380])
    t_summary.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
        ('PADDING', (0, 0), (-1, -1), 12),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(t_summary)
    story.append(Spacer(1, 15))

    # Encart Avertissement Architecture CSR / Pare-feu WAF si applicable
    if audit_data.get("isWafBlocked") or audit_data.get("wafDetails"):
        waf_d = audit_data.get("wafDetails") or {}
        is_csr = audit_data.get("auditType") == "CSR_SPA_UNRENDERED" or waf_d.get("type") == "CSR"
        blocker = _escape_xml(waf_d.get("blocker") or ("Rendu Client-Side (CSR / SPA)" if is_csr else "Pare-feu WAF"))
        advice = _escape_xml(waf_d.get("advice") or ("Activez le Server-Side Rendering (SSR) pour exposer vos fiches produits aux robots IA." if is_csr else "Autorisez les agents IA dans vos règles pare-feu."))
        impact = _escape_xml(waf_d.get("impact") or "Les crawlers IA consomment le code HTML source sans exécuter le JavaScript lourd.")
        msg = _escape_xml(waf_d.get("message") or "Contenu HTML non pré-rendu ou filtré par pare-feu.")

        waf_box_data = [
            [
                Paragraph(
                    f"<b>⚠️ AVERTISSEMENT ARCHITECTURE : {blocker.upper()}</b><br/>"
                    f"<b>Diagnostic :</b> {msg}<br/>"
                    f"<b>Impact IA :</b> {impact}<br/>"
                    f"<b>Recommandation technique :</b> {advice}",
                    normal_style
                )
            ]
        ]
        t_waf = Table(waf_box_data, colWidths=[540])
        t_waf.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fef2f2')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#ef4444')),
            ('PADDING', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(t_waf)
        story.append(Spacer(1, 12))

    # 3. Tableau des 5 Piliers
    story.append(Paragraph("Détail des 5 Piliers d'Évaluation Agentique", section_style))
    story.append(Spacer(1, 6))

    pillars = audit_data.get("pillars", {})
    p_crawl = pillars.get("crawl", {})
    p_schema = pillars.get("schema", {})
    p_tokens = pillars.get("tokens", {})
    p_sim = pillars.get("simulator", {})
    p_proto = pillars.get("proto") or pillars.get("protocols", {})

    pillars_rows = [
        [Paragraph("<b>Pilier</b>", normal_style), Paragraph("<b>Pondération</b>", normal_style), Paragraph("<b>Score</b>", normal_style), Paragraph("<b>Statut Technique</b>", normal_style)],
        [Paragraph("1. Crawl & Bot Access (robots.txt / WAF)", normal_style), Paragraph("20%", normal_style), Paragraph(f"<b>{_escape_xml(p_crawl.get('score', '--'))}/100</b>", normal_style), Paragraph(_escape_xml(p_crawl.get('status', '--')), normal_style)],
        [Paragraph("2. Schema.org & JSON-LD Déterministe", normal_style), Paragraph("25%", normal_style), Paragraph(f"<b>{_escape_xml(p_schema.get('score', '--'))}/100</b>", normal_style), Paragraph(_escape_xml(p_schema.get('status', '--')), normal_style)],
        [Paragraph("3. Pureté Sémantique & Économie de Tokens", normal_style), Paragraph("20%", normal_style), Paragraph(f"<b>{_escape_xml(p_tokens.get('score', '--'))}/100</b>", normal_style), Paragraph(_escape_xml(p_tokens.get('status', '--')), normal_style)],
        [Paragraph("4. AI Buyer Simulator (Google Gemini Flash)", normal_style), Paragraph("20%", normal_style), Paragraph(f"<b>{_escape_xml(p_sim.get('score', '--'))}/100</b>", normal_style), Paragraph(_escape_xml(p_sim.get('status', '--')), normal_style)],
        [Paragraph("5. Protocoles Agentiques (llms.txt / MCP)", normal_style), Paragraph("15%", normal_style), Paragraph(f"<b>{_escape_xml(p_proto.get('score', '--'))}/100</b>", normal_style), Paragraph(_escape_xml(p_proto.get('status', '--')), normal_style)],
    ]

    t_pillars = Table(pillars_rows, colWidths=[220, 70, 70, 180])
    t_pillars.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(t_pillars)
    story.append(Spacer(1, 15))

    # 4. Diagnostic IA Acheteuse
    story.append(Paragraph("Diagnostic de l'IA Acheteuse (Google Gemini Flash)", section_style))
    story.append(Spacer(1, 6))

    ai_view = audit_data.get("aiView", {})
    gemini_details = p_sim.get("details", [])
    if gemini_details:
        gemini_txt = "<br/>• ".join(_escape_xml(d) for d in gemini_details)
    else:
        gemini_txt = "Capacité d'achat autonome vérifiée."

    sim_table_data = [
        [Paragraph("<b>Prix extrait par l'agent :</b>", normal_style), Paragraph(_escape_xml(ai_view.get("extractedPrice", "--")), normal_style)],
        [Paragraph("<b>Disponibilité du stock :</b>", normal_style), Paragraph(_escape_xml(ai_view.get("stockStatus", "--")), normal_style)],
        [Paragraph("<b>Conditions de livraison :</b>", normal_style), Paragraph(_escape_xml(ai_view.get("shippingTerms", "--")), normal_style)],
        [Paragraph("<b>Indice de risque d'hallucination :</b>", normal_style), Paragraph(f"<b>{_escape_xml(ai_view.get('hallucinationRisk', '--'))}</b>", normal_style)],
        [Paragraph("<b>Points de contrôle analysés :</b>", normal_style), Paragraph(f"• {gemini_txt}", normal_style)],
    ]
    t_sim = Table(sim_table_data, colWidths=[180, 360])
    t_sim.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('PADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(t_sim)
    story.append(Spacer(1, 15))

    # 5. Snippet llms.txt
    auto_fix = audit_data.get("autoFix", {})
    llms_txt = auto_fix.get("llmsTxt", "")
    if llms_txt:
        story.append(Paragraph("Spécification Standard Recommandée (/.well-known/llms.txt)", section_style))
        story.append(Spacer(1, 4))
        story.append(Preformatted(llms_txt[:450] + ("\n..." if len(llms_txt) > 450 else ""), code_style))
        story.append(Spacer(1, 10))

    # Footer
    story.append(HRFlowable(width="100%", thickness=0.5, color=c_text_muted, spaceBefore=10, spaceAfter=8))
    story.append(Paragraph("Rapport certifié édité par la plateforme AgentReady. Les standards d'audit suivent les spécifications W3C Schema.org 2026 et les protocoles LLMs.txt & Model Context Protocol (MCP).", ParagraphStyle('Foot', parent=styles['Normal'], fontSize=7.5, leading=10, textColor=c_text_muted)))

    doc.build(story)
    return buffer.getvalue()

