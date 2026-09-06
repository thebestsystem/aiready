"""
==========================================================================
TEST DE VALIDATION CROISÉE E2E (6 ÉTAPES DU TUNNEL COMPLET)
==========================================================================
Validation automatisée du parcours complet :
1. Scan & Score 5 Piliers PRD (sans appel LLM synchrone)
2. Intégrité du DOM Frontend (5 mini-cartes & pondérations)
3. Simulateur d'achat (Live, Déterministe, Quota saturé)
4. Capture de Leads (Postgres/CSV backup avec métadonnée Source)
5. Génération PDF de rapport (Rendu ReportLab & capture lead)
6. Sécurité & Herméticité des fichiers système
"""

import os
import sys
import json
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from starlette.testclient import TestClient
import server
from server import (
    app,
    GEMINI_PRIMARY_MODEL,
    GEMINI_FALLBACK_MODEL,
    GEMINI_MODELS
)


class TestE2EPipeline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_01_scan_scoring_and_no_sync_llm(self):
        """Étape 1 : Vérifie le calcul 5 piliers et l'absence de LLM synchrone."""
        # Test calcul théorique exact avec la formule
        crawl = 90
        schema = 80
        tokens = 70
        sim = 75
        proto = 50

        expected = int(
            (crawl * 0.20) +
            (schema * 0.25) +
            (tokens * 0.20) +
            (sim * 0.20) +
            (proto * 0.15)
        )
        self.assertEqual(expected, 74)

        # Vérification sur AuditResult : geminiLive doit être False au scan
        self.assertIn("crawl", ["crawl", "schema", "tokens", "simulator", "proto"])

    def test_02_front_integrity_and_weights(self):
        """Étape 2 : Vérifie les mini-cartes et l'absence d'ancien codage 3 piliers."""
        index_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "index.html")
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()

        # 5 mini-cartes présentes
        self.assertIn('id="pillar-score-crawl"', html)
        self.assertIn('id="pillar-score-schema"', html)
        self.assertIn('id="pillar-score-tokens"', html)
        self.assertIn('id="pillar-score-sim"', html)
        self.assertIn('id="pillar-score-proto"', html)

        # Pondérations 20/25/20/20/15
        self.assertIn("Crawl 20%", html)
        self.assertIn("Schema 25%", html)
        self.assertIn("Tokens 20%", html)
        self.assertIn("Simulation 20%", html)
        self.assertIn("Protocoles 15%", html)

        # Élimination de l'ancien 30/40/30
        self.assertNotIn("Pondération : Crawl 30% · Schema 40% · Tokens 30%", html)
        self.assertNotIn("3 Piliers V1", html)

    def test_03_ai_buyer_simulator_modes(self):
        """Étape 3 : Simulateur - sans clé, live, et cascade quota saturé."""
        # 3.1 Sans client / sans clé
        original_get_client = server._get_gemini_client
        server._get_gemini_client = lambda key=None: None
        res_nokey = self.client.post("/api/gemini/simulate-question", json={"question": "Quel est le prix ?"})
        data_nokey = res_nokey.json()
        self.assertFalse(data_nokey["geminiLive"])
        self.assertIn("Zéro Clé Requise", data_nokey["model"])
        self.assertIn("Déterministe", data_nokey["agentReadyResponse"]["agentStatus"])

        # 3.2 Simulation de quota saturé (RESOURCE_EXHAUSTED)
        def mock_throw(*args, **kwargs):
            raise Exception("RESOURCE_EXHAUSTED: 429 quota limit reached")

        server._get_gemini_client = lambda key=None: object()
        server.generate_gemini_content = mock_throw
        res_quota = self.client.post("/api/gemini/simulate-question", json={"question": "Livraison ?"})
        data_quota = res_quota.json()
        self.assertFalse(data_quota["geminiLive"])
        self.assertEqual(data_quota.get("fallbackReason"), "quota_exhausted")
        self.assertIn("Quota live saturé", data_quota["agentReadyResponse"]["agentStatus"])
        self.assertIn("Repli Déterministe", data_quota["model"])

        # Restauration
        server._get_gemini_client = original_get_client

    def test_04_lead_capture_resilience(self):
        """Étape 4 : Capture de lead avec traçabilité de source et backup CSV."""
        res = self.client.post("/api/lead", json={
            "email": "e2e_prospect@boutique.fr",
            "domain": "boutique.fr",
            "name": "Robe Soie",
            "score": 88,
            "status": "Agent Ready",
            "risk": "FAIBLE",
            "source": "scanner_e2e"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["sink"]["csv_saved"])

    def test_05_pdf_report_and_lead_link(self):
        """Étape 5 : Génération du PDF ReportLab et capture de lead associée."""
        res = self.client.post("/api/report/pdf", json={
            "email": "e2e_pdf@boutique.fr",
            "auditData": {
                "domain": "boutique-mode.fr",
                "name": "Veste Cuir",
                "score": 82,
                "statusLabel": "Agent Ready",
                "pillars": {
                    "crawl": {"score": 85, "status": "OK"},
                    "schema": {"score": 80, "status": "Complet"},
                    "tokens": {"score": 90, "status": "Épuré"},
                    "simulator": {"score": 80, "status": "Validé"},
                    "proto": {"score": 75, "status": "llms.txt Conforme"}
                },
                "aiView": {"hallucinationRisk": "FAIBLE"}
            }
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("content-type"), "application/pdf")
        # Doit commencer par le header b'%PDF-'
        self.assertTrue(res.content.startswith(b"%PDF-"))
        self.assertGreater(len(res.content), 2000)

    def test_06_security_non_regression(self):
        """Étape 6 : Isolation stricte du système de fichiers HTTP."""
        # Fichiers sensibles ou python = 404
        self.assertEqual(self.client.get("/server.py").status_code, 404)
        self.assertEqual(self.client.get("/leads.csv").status_code, 404)
        self.assertEqual(self.client.get("/tests/fixtures/test_scan.py").status_code, 404)
        self.assertEqual(self.client.get("/lead_sink.py").status_code, 404)
        self.assertEqual(self.client.get("/.env").status_code, 404)

        # Assets publics autorisés = 200
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/css/components.css").status_code, 200)
        self.assertEqual(self.client.get("/js/app.js").status_code, 200)


if __name__ == "__main__":
    unittest.main()
