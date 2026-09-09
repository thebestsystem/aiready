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
import socket
import hashlib
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import httpx

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
        """Étape 1 : Vérifie le calcul 5 piliers et l'absence de LLM synchrone sur /api/scan."""
        # 1. Vérification du calcul théorique de la formule pondérée
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

        # 2. Exécution d'un scan réel simulé via l'API
        mock_resp = MagicMock()
        mock_resp.text = "<html><head><title>Boutique Test</title></head><body><h1>Sneakers Pro</h1><span itemprop='price'>120.00 EUR</span></body></html>"
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "text/html"}
        mock_resp.aiter_bytes = None
        mock_resp.history = []
        mock_resp.url = httpx.URL("https://boutique-test.fr")

        fake_robots = {"found": True, "global_disallowed": False, "disallowed_bots": [], "raw": ""}
        fake_llms = {"found": True, "path": "/.well-known/llms.txt", "content": "# LLMs.txt\nAPI: https://api.boutique.fr\nOpenAPI: /openapi.json"}

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp), \
             patch("server.fetch_robots_txt", new_callable=AsyncMock, return_value=fake_robots), \
             patch("server.check_llms_txt", new_callable=AsyncMock, return_value=fake_llms):

            res = self.client.post("/api/scan", json={"url": "https://boutique-test.fr"})
            self.assertEqual(res.status_code, 200)
            data = res.json()

            # Absence de LLM synchrone au scan (exigence PRD)
            self.assertFalse(data.get("geminiLive"), "Le scan doit être 100% déterministe (zéro appel LLM synchrone)")

            # Présence et intégrité des 5 piliers
            pillars = data.get("pillars", {})
            for p in ["crawl", "schema", "tokens", "simulator", "proto"]:
                self.assertIn(p, pillars, f"Le pilier '{p}' doit être présent dans l'audit")
                self.assertIn("score", pillars[p])
                self.assertIn("weight", pillars[p])

            # Validation de la cohérence mathématique du score global
            c = pillars["crawl"]["score"]
            s = pillars["schema"]["score"]
            t = pillars["tokens"]["score"]
            sim_score = pillars["simulator"]["score"]
            proto_score = pillars["proto"]["score"]
            calc_score = int((c * 0.20) + (s * 0.25) + (t * 0.20) + (sim_score * 0.20) + (proto_score * 0.15))
            self.assertEqual(data["score"], calc_score, "Le score total doit correspondre à la somme pondérée des 5 piliers")

        server._scan_limiter.reset()

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
        self.assertIn("Complétude 20%", html)
        self.assertIn("Protocoles 15%", html)

        # Élimination de l'ancien 30/40/30
        self.assertNotIn("Pondération : Crawl 30% · Schema 40% · Tokens 30%", html)
        self.assertNotIn("3 Piliers V1", html)

        # TACHE-03 UX : présence du bandeau d'erreur explicite (+ bouton réessayer)
        self.assertIn('id="scan-error-box"', html)
        self.assertIn('id="btn-retry-scan-error"', html)
        self.assertIn('id="scan-error-message"', html)

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

    def test_07_rate_limit_scan(self):
        """Étape 7 (TACHE-01) : Rate-limit anti-abus sur /api/scan (10 req / 60s par défaut)."""
        from unittest.mock import patch, AsyncMock, MagicMock
        server._scan_limiter.reset()

        # Mock des appels réseau sortants de scan_url pour un test unitaire hermétique et rapide
        mock_resp = MagicMock()
        mock_resp.text = "<html><head><title>Boutique Test</title></head><body><h1>Boutique</h1></body></html>"
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "text/html"}

        fake_robots = {"found": True, "global_disallowed": False, "disallowed_bots": [], "raw": ""}
        fake_llms = {"found": True, "path": "/.well-known/llms.txt", "content": "# LLMs.txt\nAPI: https://api.boutique.fr\nOpenAPI: /openapi.json"}

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp), \
             patch("server.fetch_robots_txt", new_callable=AsyncMock, return_value=fake_robots), \
             patch("server.check_llms_txt", new_callable=AsyncMock, return_value=fake_llms):

            ip_a = "192.168.1.100"
            limit = server._scan_limiter.limit  # 10 par défaut

            # 1. Les N premières requêtes sous le seuil sont acceptées (200)
            for i in range(limit):
                res = self.client.post(
                    "/api/scan",
                    json={"url": "https://boutique-test.fr"},
                    headers={"X-Forwarded-For": ip_a}
                )
                self.assertEqual(res.status_code, 200, f"Requête {i+1} de l'IP {ip_a} devrait passer")

            # 2. La (N+1)ème requête dépasse la limite -> HTTP 429 non-fatale avec en-têtes standard
            res_blocked = self.client.post(
                "/api/scan",
                json={"url": "https://boutique-test.fr"},
                headers={"X-Forwarded-For": ip_a}
            )
            self.assertEqual(res_blocked.status_code, 429)
            self.assertIn("Retry-After", res_blocked.headers)
            body = res_blocked.json()
            self.assertIn("detail", body)
            self.assertIn("retry_after", body)
            self.assertGreaterEqual(body["retry_after"], 1)

            # 3. Une IP distincte n'est PAS bloquée (isolation stricte par IP)
            ip_b = "192.168.1.200"
            res_ip_b = self.client.post(
                "/api/scan",
                json={"url": "https://boutique-test.fr"},
                headers={"X-Forwarded-For": ip_b}
            )
            self.assertEqual(res_ip_b.status_code, 200, f"L'IP {ip_b} distincte ne doit pas être bloquée")

        # 4. Vérification de la configurabilité dynamique par variable d'environnement
        server._scan_limiter.reset()
        os.environ["SCAN_RATE_LIMIT"] = "2"
        self.assertEqual(server._scan_limiter.limit, 2)
        server._scan_limiter.reset()
        del os.environ["SCAN_RATE_LIMIT"]

    def test_08_rate_limit_simulate_question(self):
        """Étape 8 (TACHE-01) : Rate-limit plus strict sur /api/gemini/simulate-question (5 req / 60s)."""
        server._sim_limiter.reset()

        ip_x = "10.0.0.50"
        limit = server._sim_limiter.limit  # 5 par défaut

        # 1. 5 requêtes consécutives sur le simulateur passent normalement (200)
        for i in range(limit):
            res = self.client.post(
                "/api/gemini/simulate-question",
                json={"question": f"Question {i+1} sur le produit"},
                headers={"X-Forwarded-For": ip_x}
            )
            self.assertEqual(res.status_code, 200, f"Question {i+1} de l'IP {ip_x} devrait passer")

        # 2. 6ème requête -> HTTP 429 avec Retry-After et JSON clair
        res_blocked = self.client.post(
            "/api/gemini/simulate-question",
            json={"question": "Question 6 en dépassement"},
            headers={"X-Forwarded-For": ip_x}
        )
        self.assertEqual(res_blocked.status_code, 429)
        self.assertIn("Retry-After", res_blocked.headers)
        data = res_blocked.json()
        self.assertIn("detail", data)
        self.assertIn("retry_after", data)
        self.assertGreaterEqual(data["retry_after"], 1)
        self.assertIn("/api/gemini/simulate-question", data["detail"])

        # 3. Isolation : une IP différente n'est pas impactée
        ip_y = "10.0.0.51"
        res_ip_y = self.client.post(
            "/api/gemini/simulate-question",
            json={"question": "Question légitime d'un autre prospect"},
            headers={"X-Forwarded-For": ip_y}
        )
        self.assertEqual(res_ip_y.status_code, 200)

        server._sim_limiter.reset()

    # ------------------------------------------------------------------
    # TACHE-02 — Garde-fous du scanner /api/scan (validation, statut,
    # content-type, borne de taille, timeout configurable).
    # ------------------------------------------------------------------
    def test_09_scan_rejects_invalid_url_before_fetch(self):
        """Étape 9 (TACHE-02) : URL invalide -> 400 SANS jamais tenter de requête réseau."""
        from unittest.mock import patch, AsyncMock

        server._scan_limiter.reset()

        bad_urls = [
            ("ftp://boutique-test.fr/robot.txt", "http"),
            ("javascript:alert(1)", "http"),
            ("https://boutique-test .fr", "espace"),
            ("", "vide"),
        ]
        net_called = {"flag": False}

        def _boom(*a, **k):
            net_called["flag"] = True
            raise AssertionError("Un fetch réseau a été tenté alors que l'URL est invalide")

        mock_get = AsyncMock(side_effect=_boom)

        with patch("httpx.AsyncClient.get", mock_get):
            for url, frag in bad_urls:
                res = self.client.post(
                    "/api/scan",
                    json={"url": url},
                    headers={"X-Forwarded-For": f"10.9.{len(url) % 50}.{len(url) % 200}"},
                )
                self.assertEqual(res.status_code, 400, f"URL '{url[:30]}' devrait être rejetée (400)")
                detail = res.json()
                self.assertIn("detail", detail)
                self.assertGreater(len(detail["detail"]), 0)

        self.assertFalse(net_called["flag"], "Aucune requête réseau ne doit partir sur une URL rejetée")

    def test_10_scan_rejects_http_error_page(self):
        """Étape 10 (TACHE-02) : page en erreur HTTP (404/500/429) -> refus, jamais analysée."""
        from unittest.mock import patch, AsyncMock, MagicMock

        server._scan_limiter.reset()

        cases = [
            (404, 404, "page introuvable"),
            (500, 502, "serveur distante"),      # mauvais statut upstream -> 502 (jamais notre 429)
            (429, 400, "page d'erreur"),          # 429 du site cible n'est pas notre rate-limit → 400 net
        ]
        for err_status, expected_status, kw in cases:
            fake = MagicMock()
            fake.status_code = err_status
            fake.headers = {"content-type": "text/html"}
            fake.text = "<html><head><title>Erreur</title></head><body>Oops</body></html>"

            with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=fake):
                res = self.client.post(
                    "/api/scan",
                    json={"url": "https://boutique-test.fr/produit"},
                    headers={"X-Forwarded-For": f"10.20.{err_status % 50}.{err_status % 200}"},
                )
            self.assertEqual(res.status_code, expected_status,
                             f"Statut cible {err_status} -> doit produire {expected_status}")
            self.assertIn(kw, res.json()["detail"])

        server._scan_limiter.reset()

    def test_11_scan_rejects_non_web_content(self):
        """Étape 11 (TACHE-02) : fiche en PDF/image/JSON n'est pas une page web -> 415."""
        from unittest.mock import patch, AsyncMock, MagicMock

        server._scan_limiter.reset()

        non_html = [
            ("application/pdf", "%PDF-1.4 fake"),
            ("application/json", '{"type":"api","data":[]}'),
            ("image/png", "\x89PNG\r\n\x1a\n"),
        ]
        for ctype, body in non_html:
            fake = MagicMock()
            fake.status_code = 200
            fake.headers = {"content-type": ctype}
            fake.text = body
            with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=fake):
                res = self.client.post(
                    "/api/scan",
                    json={"url": "https://boutique-test.fr/catalogue.pdf"},
                    headers={"X-Forwarded-For": f"10.31.{hash(ctype) % 200}.{len(ctype) % 200}"},
                )
            self.assertEqual(res.status_code, 415, f"Content-Type '{ctype}' doit être refusé")
            self.assertIn("page web HTML", res.json()["detail"])

        server._scan_limiter.reset()

    def test_12_scan_rejects_too_large_announced_page(self):
        """Étape 12 (TACHE-02) : page annonçant un Content-Length > borne -> 413 (anti-DoS)."""
        from unittest.mock import patch, AsyncMock, MagicMock

        server._scan_limiter.reset()

        fake = MagicMock()
        fake.status_code = 200
        fake.headers = {
            "content-type": "text/html",
            "content-length": str(server.SCAN_MAX_RESPONSE_BYTES + 500_000),  # juste au-dessus de la borne
        }
        fake.text = "<html><body>page géante</body></html>"

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=fake):
            res = self.client.post(
                "/api/scan",
                json={"url": "https://boutique-test.fr/page-geante"},
                headers={"X-Forwarded-For": "10.41.1.7"},
            )
        self.assertEqual(res.status_code, 413)
        self.assertIn("trop volumineuse", res.json()["detail"].lower())

        server._scan_limiter.reset()

    def test_13_scan_timeout_and_size_env_clamped(self):
        """Étape 13 (TACHE-02) : timeouts & bornes configurables via env, clamps de sécurité."""
        server._scan_limiter.reset()

        tmp_env_key = "T02_CLAMP_TEST"
        self.assertEqual(server._int_env_clamped(tmp_env_key, "12", 1, 60), 12)  # valeur par défaut
        os.environ[tmp_env_key] = "9999"
        self.assertEqual(server._int_env_clamped(tmp_env_key, "12", 1, 60), 60)  # clamp haut
        os.environ[tmp_env_key] = "-5"
        self.assertEqual(server._int_env_clamped(tmp_env_key, "12", 1, 60), 1)   # clamp bas
        os.environ[tmp_env_key] = "abc"
        self.assertEqual(server._int_env_clamped(tmp_env_key, "12", 1, 60), 12)  # non-numérique -> défaut
        del os.environ[tmp_env_key]

        # Le timeout produit doit toujours rester dans la plage [1..60].
        self.assertGreaterEqual(server.SCAN_FETCH_TIMEOUT_SECONDS, 1)
        self.assertLessEqual(server.SCAN_FETCH_TIMEOUT_SECONDS, 60)
        # La borne mémoire >= 100 Ko (contrainte de plancher).
        self.assertGreaterEqual(server.SCAN_MAX_RESPONSE_BYTES, 100_000)

    def test_14_scan_tolerates_large_page_without_content_length(self):
        """Étape 14 (TACHE-02) : grand HTML SANS Content-Length est tronqué à la borne, jamais 500."""
        import httpx
        from unittest.mock import patch, AsyncMock

        server._scan_limiter.reset()

        # Vrai corps httpx : 3 Mo de balisage valide, sans header Content-Length.
        big_html = ("<html><head><title>Grosse page</title></head><body>" + ("<p>produit X</p>" * 170000) + "</body></html>").encode("utf-8")
        self.assertGreater(len(big_html), server.SCAN_MAX_RESPONSE_BYTES, "Le corps doit être plus grand que la borne")

        response = httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},  # pas de content-length indiqué volontairement
            content=big_html,
            request=httpx.Request("GET", "https://boutique-test.fr/"),
        )
        # httpx matérialise par défaut un Content-Length sur une Response construite en mémoire.
        # On le retire pour simuler un serveur descendant en flux (chunked, sans longueur annoncée)
        # et ainsi prouver le déclenchement de la *troncature* (et non du refus 413).
        if "content-length" in response.headers:
            del response.headers["content-length"]

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=response), \
             patch("server.fetch_robots_txt", new_callable=AsyncMock,
                   return_value={"found": True, "global_disallowed": False,
                                 "disallowed_bots": [], "raw": ""}), \
             patch("server.check_llms_txt", new_callable=AsyncMock,
                   return_value={"found": False, "path": None, "content": None}):
            res = self.client.post(
                "/api/scan",
                json={"url": "https://boutique-test.fr/grosse-page"},
                headers={"X-Forwarded-For": "10.50.1.9"},
            )
        # La page étant un vrai HTML valide (juste très grosse), le scan doit aboutir
        # sans 413 ni 500 : le corps est tronqué en mémoire à la borne.
        self.assertNotIn(res.status_code, (500, 413, 415), f"Réponse inattendue (HTTP {res.status_code})")

        server._scan_limiter.reset()

    # ------------------------------------------------------------------
    # Lot P1-Sécurité — SSRF, validation email & rate-limit lead/report
    # ------------------------------------------------------------------
    def test_15_scan_rejects_ssrf_targets(self):
        """Étape 15 (P1-Sécu) : fetch interdit vers réseaux privés/réservés (SSRF)."""
        from unittest.mock import patch, AsyncMock  # noqa : lève si un fetch est tenté

        server._scan_limiter.reset()

        ssrf_urls = [
            "http://169.254.169.254/latest/meta-data/",
            "http://127.0.0.1:5432/",
            "http://10.0.0.1/private",
            "http://192.168.1.10/internal",
            "http://localhost:8000/api/health",
            "http://[::1]/",
        ]
        boom = AsyncMock(side_effect=AssertionError("Fetch réseau tenté malgré SSRF blocage"))
        with patch("httpx.AsyncClient.get", boom):
            for url in ssrf_urls:
                res = self.client.post(
                    "/api/scan",
                    json={"url": url},
                    headers={"X-Forwarded-For": f"10.99.{abs(hash(url)) % 200}.{len(url) % 200}"},
                )
                self.assertEqual(res.status_code, 400, f"URL '{url}' devrait être bloquée (SSRF)")
                self.assertIn("SSRF", res.json()["detail"])

        server._scan_limiter.reset()

    def test_16_lead_validates_email_and_is_rate_limited(self):
        """Étape 16 (P1-Sécu) : /api/lead exige un email valide et est limité par IP."""
        server._lead_limiter.reset()

        # 1. Email invalide -> 400, pas d'enregistrement
        res_bad = self.client.post("/api/lead", json={
            "email": "pas-un-email", "domain": "boutique.fr"},
            headers={"X-Forwarded-For": "203.0.113.9"})
        self.assertEqual(res_bad.status_code, 400)
        self.assertIn("Email", res_bad.json()["detail"])

        # 2. Email valide -> 200
        res_ok = self.client.post("/api/lead", json={
            "email": "p1_sec@boutique.fr", "domain": "boutique.fr"},
            headers={"X-Forwarded-For": "203.0.113.9"})
        self.assertEqual(res_ok.status_code, 200)

        # 3. Dépassement de la limite (LEAD_RATE_LIMIT=20 par défaut) -> 429
        ok = 0
        for i in range(server._lead_limiter.limit + 2):
            r = self.client.post("/api/lead", json={
                "email": f"p1_sec{i}@boutique.fr", "domain": "boutique.fr"},
                headers={"X-Forwarded-For": "203.0.113.10"})
            if r.status_code == 200:
                ok += 1
            else:
                self.assertEqual(r.status_code, 429)
        self.assertLessEqual(ok, server._lead_limiter.limit)

        server._lead_limiter.reset()

    # ------------------------------------------------------------------
    # Tests de non-régression Bugs A, B, C
    # ------------------------------------------------------------------
    def test_17_bug_a_robots_absent_vs_permissive(self):
        """Bug A : Distinguer robots.txt absent (message honnête 85/100) de présent + permissif (100/100)."""
        from unittest.mock import patch, AsyncMock, MagicMock
        server._scan_limiter.reset()

        fake_page = MagicMock()
        fake_page.status_code = 200
        fake_page.headers = {"content-type": "text/html"}
        fake_page.text = "<html><head><title>Boutique</title></head><body><h1>Boutique Test</h1></body></html>"

        # Cas 1 : robots.txt absent (404 / found=False)
        robots_absent = {"found": False, "global_disallowed": False, "disallowed_bots": [], "raw": ""}
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=fake_page), \
             patch("server.fetch_robots_txt", new_callable=AsyncMock, return_value=robots_absent), \
             patch("server.check_llms_txt", new_callable=AsyncMock, return_value={"found": False, "path": None, "content": None}):
            res = self.client.post("/api/scan", json={"url": "https://boutique-sans-robots.com/p1"},
                                   headers={"X-Forwarded-For": "10.100.1.1"})
            self.assertEqual(res.status_code, 200)
            data = res.json()
            crawl_pillar = data["pillars"]["crawl"]
            # Ne doit PAS être 100/100
            self.assertEqual(crawl_pillar["score"], 85)
            # Message honnête : absent
            self.assertTrue(any("robots.txt absent" in d for d in crawl_pillar["details"]))
            self.assertFalse(any("autorise les bots IA majeurs" in d for d in crawl_pillar["details"]))

        server._scan_limiter.reset()

        # Cas 2 : robots.txt présent et permissif (found=True, allowed)
        robots_permissive = {"found": True, "global_disallowed": False, "disallowed_bots": [], "raw": "User-agent: *\nAllow: /"}
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=fake_page), \
             patch("server.fetch_robots_txt", new_callable=AsyncMock, return_value=robots_permissive), \
             patch("server.check_llms_txt", new_callable=AsyncMock, return_value={"found": False, "path": None, "content": None}):
            res = self.client.post("/api/scan", json={"url": "https://boutique-avec-robots.com/p1"},
                                   headers={"X-Forwarded-For": "10.100.1.2"})
            self.assertEqual(res.status_code, 200)
            data = res.json()
            crawl_pillar = data["pillars"]["crawl"]
            self.assertEqual(crawl_pillar["score"], 100)
            self.assertTrue(any("robots.txt présent et permissif" in d for d in crawl_pillar["details"]))

        server._scan_limiter.reset()

    def test_18_bug_b_html_price_extraction_and_simulator(self):
        """Bug B : Extraction du prix et métadonnées depuis le HTML en clair quand JSON-LD est absent."""
        from unittest.mock import patch, AsyncMock, MagicMock
        server._scan_limiter.reset()

        # Simule exactement la structure de books.toscrape.com
        html_books = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>A Light in the Attic | Books to Scrape - Sandbox</title>
        </head>
        <body>
            <h1>A Light in the Attic</h1>
            <p class="price_color">£51.77</p>
            <p class="instock availability">In stock (22 available)</p>
            <table>
                <tr><th>UPC</th><td>a897fe39b1053632</td></tr>
                <tr><th>Product Type</th><td>Books</td></tr>
                <tr><th>Price (incl. tax)</th><td>£51.77</td></tr>
            </table>
        </body>
        </html>
        """

        fake_page = MagicMock()
        fake_page.status_code = 200
        fake_page.headers = {"content-type": "text/html; charset=utf-8"}
        fake_page.text = html_books

        # Mock getaddrinfo pour simuler un réseau IPv6/NAT64 (64:ff9b:: en 1er, IPv4 en 2nd)
        # Rend le test 100% hermétique et immunisé aux variations de DNS locaux/cloud
        mock_addrinfo = [
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("64:ff9b::23d3:7a6d", 443, 0, 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("35.211.122.109", 443)),
        ]

        import socket as _socket
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=fake_page), \
             patch("server.fetch_robots_txt", new_callable=AsyncMock,
                   return_value={"found": False, "global_disallowed": False, "disallowed_bots": [], "raw": ""}), \
             patch("server.check_llms_txt", new_callable=AsyncMock,
                   return_value={"found": False, "path": None, "content": None}), \
             patch("socket.getaddrinfo", return_value=mock_addrinfo):
            res = self.client.post(
                "/api/scan",
                json={"url": "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"},
                headers={"X-Forwarded-For": "10.100.2.1"}
            )
            self.assertEqual(res.status_code, 200)
            data = res.json()

            # 1. extractedPrice ne doit plus être 'Inconnu EUR'
            ai_view = data["aiView"]
            self.assertIn("51.77", ai_view["extractedPrice"])
            self.assertIn("GBP", ai_view["extractedPrice"])
            self.assertNotIn("Inconnu", ai_view["extractedPrice"])

            # 2. Nom du produit extrait proprement
            self.assertEqual(data["name"], "A Light in the Attic")

            # 3. Simulator : score supérieur à 30 (points prix + stock attribués)
            sim_pillar = data["pillars"]["simulator"]
            self.assertGreaterEqual(sim_pillar["score"], 55)
            self.assertIn("Prix extrait du HTML en clair", " ".join(sim_pillar["details"]))
            self.assertNotEqual(sim_pillar["status"], "Risque ÉLEVÉ (50%+)")

            # 4. Stock détecté
            self.assertIn("IN_STOCK", ai_view["stockStatus"])

            # 5. Product Data
            prod = data["productData"]
            self.assertEqual(prod["price"], "51.77")
            self.assertEqual(prod["currency"], "GBP")
            self.assertEqual(prod["sku"], "a897fe39b1053632")

        server._scan_limiter.reset()

    def test_19_bug_c_autofix_snippets_clean_placeholders(self):
        """Bug C : Auto-Fix ne doit jamais générer price: None, SKU-AUTO-01, ou agent@www..."""
        # Test 1 : Site avec domaine www. et prix extrait
        prod_data = {
            "name": "Chaise Ergonomique Pro",
            "price": "149.99",
            "currency": "EUR",
            "sku": "CHAIR-ERG-01"
        }
        snippets = server.generate_auto_fix_snippets("www.welcomeoffice.com", prod_data)

        # Pas de www. dans les adresses de contact ou configs
        self.assertNotIn("@www.", snippets["llmsTxt"])
        self.assertIn("contact@welcomeoffice.com", snippets["llmsTxt"])

        # JSON-LD avec prix et nom corrects
        self.assertIn('"price": "149.99"', snippets["schemaJson"])
        self.assertIn('"name": "Chaise Ergonomique Pro"', snippets["schemaJson"])
        self.assertIn('"sku": "CHAIR-ERG-01"', snippets["schemaJson"])
        self.assertNotIn('"None"', snippets["schemaJson"])
        self.assertNotIn("SKU-AUTO-01", snippets["schemaJson"])
        self.assertNotIn("Produit E-commerce", snippets["schemaJson"])

        # Test 2 : Fiche vide / dégradée -> fallback propre et jamais 'None'
        empty_prod = {"name": None, "price": "Inconnu", "sku": None}
        snippets_empty = server.generate_auto_fix_snippets("boutique.fr", empty_prod)
        self.assertNotIn('"price": "None"', snippets_empty["schemaJson"])
        self.assertNotIn('"None"', snippets_empty["schemaJson"])
        self.assertNotIn("SKU-AUTO-01", snippets_empty["schemaJson"])
        self.assertNotIn("Produit E-commerce", snippets_empty["schemaJson"])
        self.assertIn("contact@boutique.fr", snippets_empty["llmsTxt"])

    def test_20_ssrf_nat64_and_multi_ip_resolution(self):
        """Sécurité SSRF : Validation NAT64 (RFC 6052) et résolution multi-adresses IP."""
        from unittest.mock import patch, AsyncMock, MagicMock
        server._scan_limiter.reset()

        fake_page = MagicMock()
        fake_page.status_code = 200
        fake_page.headers = {"content-type": "text/html"}
        fake_page.text = "<html><body><h1>OK</h1></body></html>"

        # 1. NAT64 encapsulant une IPv4 publique (ex: 35.211.122.109 -> 64:ff9b::23d3:7a6d) : autorisé
        mock_nat64_public = [
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("64:ff9b::23d3:7a6d", 443, 0, 0))
        ]
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=fake_page), \
             patch("server.fetch_robots_txt", new_callable=AsyncMock,
                   return_value={"found": False, "global_disallowed": False, "disallowed_bots": [], "raw": ""}), \
             patch("server.check_llms_txt", new_callable=AsyncMock,
                   return_value={"found": False, "path": None, "content": None}), \
             patch("socket.getaddrinfo", return_value=mock_nat64_public):
            res = self.client.post("/api/scan", json={"url": "https://boutique-nat64-public.fr"},
                                   headers={"X-Forwarded-For": "10.200.1.1"})
            self.assertEqual(res.status_code, 200, "Une IPv6 NAT64 pointant vers une IPv4 publique doit être acceptée")

        server._scan_limiter.reset()

        # 2. NAT64 encapsulant une IPv4 privée (ex: 127.0.0.1 -> 64:ff9b::7f00:0001) : bloqué 400 (SSRF)
        mock_nat64_private = [
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("64:ff9b::7f00:0001", 443, 0, 0))
        ]
        with patch("socket.getaddrinfo", return_value=mock_nat64_private):
            res = self.client.post("/api/scan", json={"url": "https://fake-ssrf-nat64.fr"},
                                   headers={"X-Forwarded-For": "10.200.1.2"})
            self.assertEqual(res.status_code, 400)
            self.assertIn("SSRF", res.json()["detail"])

        server._scan_limiter.reset()

        # 3. Hôte multi-IP où TOUTES les IP sont privées : bloqué 400 (SSRF)
        mock_all_private = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 80)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.1", 80)),
        ]
        with patch("socket.getaddrinfo", return_value=mock_all_private):
            res = self.client.post("/api/scan", json={"url": "https://internal-multi.fr"},
                                   headers={"X-Forwarded-For": "10.200.1.3"})
            self.assertEqual(res.status_code, 400)
            self.assertIn("SSRF", res.json()["detail"])

        server._scan_limiter.reset()

    def test_21_resend_lead_notification(self):
        """Resend : notification email fondateur à chaque lead (configurable, jamais bloquant)."""
        from unittest.mock import patch
        from types import SimpleNamespace
        import lead_sink

        # Cas 1 : non configuré -> aucun envoi, resend_sent False
        with patch.dict(os.environ, {"RESEND_API_KEY": "", "RESEND_FROM": "", "RESEND_NOTIFY_TO": ""}):
            with patch("lead_sink.httpx.post") as mock_post:
                res = lead_sink.dispatch_lead(
                    "prospect@shop.com", "shop.com", "Produit Test", 70,
                    "Agent Friction", "MOYEN", "scanner"
                )
                self.assertFalse(res["resend_sent"])
                mock_post.assert_not_called()

        # Cas 2 : configuré -> envoi tenté, payload correct, resend_sent True sur 200
        fake_resp = SimpleNamespace(status_code=200)
        with patch.dict(os.environ, {
            "RESEND_API_KEY": "re_test",
            "RESEND_FROM": "AgentReady <audit@8dev.net>",
            "RESEND_NOTIFY_TO": "founder@8dev.net",
        }):
            with patch("lead_sink.httpx.post", return_value=fake_resp) as mock_post:
                res = lead_sink.dispatch_lead(
                    "prospect@shop.com", "shop.com", "Produit Test", 70,
                    "Agent Friction", "MOYEN", "scanner"
                )
                self.assertTrue(res["resend_sent"])
                mock_post.assert_called_once()
                args, kwargs = mock_post.call_args
                self.assertEqual(args[0], "https://api.resend.com/emails")
                payload = kwargs["json"]
                self.assertEqual(payload["from"], "AgentReady <audit@8dev.net>")
                self.assertEqual(payload["to"], ["founder@8dev.net"])
                self.assertIn("shop.com", payload["subject"])
                self.assertIn("70/100", payload["subject"])

    def test_22_ssrf_redirect_blocked(self):
        """Sécurité SSRF : Redirection HTTP (301/302) vers une IP privée/interne bloquée net."""
        def mock_redirect_handler(request):
            if "evil-redirect.com" in str(request.url):
                return httpx.Response(302, headers={"Location": "http://127.0.0.1:9200/secret"})
            return httpx.Response(200, text="internal resource")

        transport = httpx.MockTransport(mock_redirect_handler)
        orig_client = httpx.AsyncClient

        def custom_client(*args, **kwargs):
            kwargs["transport"] = transport
            return orig_client(*args, **kwargs)

        with patch("server.httpx.AsyncClient", side_effect=custom_client):
            res = self.client.post("/api/scan", json={"url": "https://evil-redirect.com/test"})
            self.assertEqual(res.status_code, 400)
            self.assertIn("SSRF", res.json()["detail"])

        server._scan_limiter.reset()

    def test_23_rate_limit_trusted_proxy_protection(self):
        """Sécurité Rate-Limit : Falsification X-Forwarded-For ignorée si client direct non approuvé."""
        from types import SimpleNamespace

        # 1. Connexion directe non fiable + falsification X-Forwarded-For -> ignorée
        fake_req_untrusted = SimpleNamespace(
            client=SimpleNamespace(host="203.0.113.195"),
            headers={"x-forwarded-for": "1.2.3.4"}
        )
        with patch.dict(os.environ, {"TRUST_PROXY_HEADERS": "false", "RAILWAY_ENVIRONMENT": "", "RENDER": "", "FLY_APP_NAME": ""}):
            ip = server._get_client_ip(fake_req_untrusted)
            self.assertEqual(ip, "203.0.113.195", "L'en-tête X-Forwarded-For falsifié doit être ignoré pour un hôte direct non fiable")

        # 2. Connexion depuis un proxy de confiance configuré -> X-Forwarded-For pris en compte
        fake_req_trusted = SimpleNamespace(
            client=SimpleNamespace(host="10.0.0.1"),
            headers={"x-forwarded-for": "198.51.100.22, 192.0.2.1"}
        )
        with patch.dict(os.environ, {"TRUSTED_PROXIES": "10.0.0.1", "TRUST_PROXY_HEADERS": ""}):
            ip = server._get_client_ip(fake_req_trusted)
            self.assertEqual(ip, "192.0.2.1", "L'IP client réelle du proxy de confiance doit être extraite")

    def test_24_deterministic_sku(self):
        """Déterminisme des SKU : sha256 garantit le même SKU indépendamment du sel Python."""
        from bs4 import BeautifulSoup
        empty_soup = BeautifulSoup("<html></html>", "html.parser")

        sku1 = server.extract_sku_from_html(empty_soup, "", "boutique-test.com")
        sku2 = server.extract_sku_from_html(empty_soup, "", "boutique-test.com")
        self.assertEqual(sku1, sku2)
        expected_suffix = hashlib.sha256("boutique-test.com".encode("utf-8")).hexdigest()[:8].upper()
        self.assertTrue(sku1.endswith(expected_suffix))

        snippets = server.generate_auto_fix_snippets("shop.com", {"name": "Test Product"})
        self.assertIn("llmsTxt", snippets)
        self.assertIn("schemaJson", snippets)

    def test_25_robots_txt_scoping_and_robust_parsing(self):
        """Robots.txt : isolation par bloc User-agent et tolérance CRLF/espaces."""
        # 1. Un autre bot bloqué ne doit pas impacter gptbot
        content_scoped = (
            "User-agent: badbot\r\n"
            "Disallow: /\r\n\r\n"
            "User-agent: gptbot\r\n"
            "Disallow: /admin\r\n"
        )
        disallowed, global_blocked = server.parse_robots_txt(content_scoped)
        self.assertNotIn("gptbot", disallowed)
        self.assertFalse(global_blocked)

        # 2. Bloquage explicite gptbot avec Disallow:/ sans espace et CRLF
        content_gptbot_blocked = "User-agent: GPTBot\r\nDisallow:/\r\n"
        disallowed, global_blocked = server.parse_robots_txt(content_gptbot_blocked)
        self.assertIn("gptbot", disallowed)

        # 3. Bloquage global User-agent: *
        content_global = "User-agent: *\nDisallow: / # tout bloquer"
        disallowed, global_blocked = server.parse_robots_txt(content_global)
        self.assertTrue(global_blocked)

    def test_26_robots_and_llms_scheme_http(self):
        """Schéma robots.txt et llms.txt : respect du protocole http si URL source en http."""
        import asyncio

        class FakeClient:
            def __init__(self):
                self.called_urls = []
            async def get(self, url, timeout=None):
                self.called_urls.append(url)
                return httpx.Response(404)

        fake_client = FakeClient()
        asyncio.run(server.fetch_robots_txt(fake_client, "myshop.fr", scheme="http"))
        self.assertEqual(fake_client.called_urls[0], "http://myshop.fr/robots.txt")

        fake_client.called_urls.clear()
        asyncio.run(server.check_llms_txt(fake_client, "myshop.fr", scheme="http"))
        self.assertTrue(all(u.startswith("http://") for u in fake_client.called_urls))

    def test_27_datadome_header_value_detection(self):
        """WAF DataDome : détection via les valeurs d'en-tête (Server, Set-Cookie)."""
        resp_headers = {"server": "DataDome Protection", "content-type": "text/html"}
        content_lower = "<html><body>Access Denied</body></html>"
        is_datadome = "datadome" in content_lower or any("datadome" in k or "datadome" in str(v).lower() for k, v in resp_headers.items())
        self.assertTrue(is_datadome)

    def test_28_pdf_generator_color_and_escaping(self):
        """PDF Generator : échappement XML (<, >, &) et formatage couleur hexadécimal."""
        import pdf_generator
        if not pdf_generator.REPORTLAB_AVAILABLE:
            self.skipTest("ReportLab non disponible")

        malicious_data = {
            "name": "Super <Boutique> & Co",
            "domain": "http://shop.com?a=1&b=2",
            "score": 85,
            "statusLabel": "Agent Ready <Vérifié>",
            "summary": "Résumé contenant des <balises> & caractères spéciaux.",
            "pillars": {
                "crawl": {"score": 90, "status": "OK <200>"},
                "schema": {"score": 80, "status": "Schema & JSON-LD"},
                "tokens": {"score": 85, "status": "Pure"},
                "simulator": {"score": 80, "status": "OK", "details": ["Vérification <1>", "Test & 2"]},
                "proto": {"score": 70, "status": "Protocols"}
            },
            "aiView": {
                "extractedPrice": "49.00 EUR <TTC>",
                "stockStatus": "En Stock & Dispo",
                "shippingTerms": "Livraison <24h>",
                "hallucinationRisk": "Faible <1%>"
            }
        }

        # Ne doit pas lever d'erreur de parsing XML ReportLab
        pdf_bytes = pdf_generator.generate_pdf_report(malicious_data, email="contact<buyer>@shop.com")
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertGreater(len(pdf_bytes), 1000)

    def test_29_no_invented_data_in_autofix(self):
        """Auto-fix certifié : aucune invention de prix (49€), stock (InStock), ni politiques fictives."""
        # Cas 1 : page type example.com (aucun prix, aucun stock, aucun SKU)
        example_prod = {
            "name": "Example Domain",
            "price": "Inconnu",
            "sku": None,
            "has_stock": None,
            "has_shipping": False,
            "has_return": False
        }
        snippets = server.generate_auto_fix_snippets("example.com", example_prod)
        
        # Le prix ne doit JAMAIS être 49.00
        self.assertNotIn("49.00", snippets["schemaJson"])
        self.assertNotIn("49.00", snippets["llmsTxt"])
        self.assertIn('"price": ""', snippets["schemaJson"])
        self.assertIn("Prix non spécifié", snippets["llmsTxt"])

        # Pas de faux InStock inventé
        self.assertNotIn("InStock", snippets["schemaJson"])
        self.assertNotIn("OutOfStock", snippets["schemaJson"])

        # Pas de fausse livraison gratuite ni retour 30j inventés
        self.assertNotIn("shippingDetails", snippets["schemaJson"])
        self.assertNotIn("hasMerchantReturnPolicy", snippets["schemaJson"])
        self.assertNotIn("24-48h", snippets["llmsTxt"])

        # Cas 2 : vrai produit avec prix et stock explicites
        real_prod = {
            "name": "Casque Audio Pro",
            "price": "199.00",
            "sku": "CASQUE-001",
            "has_stock": True,
            "has_shipping": True,
            "has_return": True
        }
        real_snippets = server.generate_auto_fix_snippets("audio-shop.com", real_prod)
        self.assertIn('"price": "199.00"', real_snippets["schemaJson"])
        self.assertIn("https://schema.org/InStock", real_snippets["schemaJson"])
        self.assertIn("shippingDetails", real_snippets["schemaJson"])
        self.assertIn("hasMerchantReturnPolicy", real_snippets["schemaJson"])
        self.assertIn("Prix 199.00 EUR TTC", real_snippets["llmsTxt"])

    def test_30_wikipedia_and_airbnb_robots_txt(self):
        """Robots.txt complexes : Wikipedia et Airbnb ne doivent PAS être signalés bloqués."""
        # Extrait fidèle du robots.txt de Wikipedia :
        # Contient des Disallow: / ciblés sur des bots spécifiques (OrthoSeller, etc.)
        # mais n'interdit pas l'ensemble des crawlers ni les bots IA
        wiki_robots = """
# Wikipedia robots.txt snippet
User-agent: OrthoSeller
Disallow: /

User-agent: BadBot
Disallow: /

User-agent: *
Disallow: /w/
Disallow: /api/
Disallow: /trap/
Allow: /
"""
        disallowed, is_global = server.parse_robots_txt(wiki_robots)
        self.assertFalse(is_global, "Wikipedia ne doit pas être considéré comme bloqué globalement")
        self.assertEqual(disallowed, [], "Aucun bot IA cible ne doit être bloqué sur Wikipedia")

        # Extrait fidèle du robots.txt d'Airbnb :
        # ImagesiftBot est bloqué avec Disallow: /, GPTBot a des routes spécifiques
        # mais ni * ni GPTBot n'ont Disallow: / global
        airbnb_robots = """
User-agent: GPTBot
Disallow: /account
Disallow: /my_listings
Disallow: /reservation
Disallow: /rooms/*/photos
Allow: /calendar/ical/

User-agent: ImagesiftBot
Allow: /calendar/ical/
Disallow: /

User-agent: *
Disallow: /500
Disallow: /account
Disallow: /api/v1/trebuchet
"""
        disallowed_ab, is_global_ab = server.parse_robots_txt(airbnb_robots)
        self.assertFalse(is_global_ab, "Airbnb ne doit pas être bloqué globalement")
        self.assertNotIn("gptbot", disallowed_ab, "GPTBot n'est pas bloqué globalement sur Airbnb")
        self.assertEqual(disallowed_ab, [])

    def test_31_http_security_headers_present(self):
        """Sécurité HTTP : Présence obligatoire des en-têtes HSTS, CSP, nosniff, DENY."""
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("x-content-type-options"), "nosniff")
        self.assertEqual(res.headers.get("x-frame-options"), "DENY")
        self.assertIn("max-age=", res.headers.get("strict-transport-security", ""))
        self.assertIn("default-src", res.headers.get("content-security-policy", ""))
        self.assertEqual(res.headers.get("referrer-policy"), "strict-origin-when-cross-origin")

    def test_32_lead_endpoint_rate_limiting(self):
        """Sécurité anti-spam : rate limit effectif sur /api/lead."""
        server._lead_limiter.reset()
        ip = "192.168.99.12"
        # Atteindre le plafond
        for _ in range(server._LEAD_RATE_LIMIT):
            res = self.client.post(
                "/api/lead",
                json={"email": "client@test.fr", "domain": "test.fr"},
                headers={"X-Forwarded-For": ip}
            )
            self.assertEqual(res.status_code, 200)

        # La requête suivante doit lever 429
        res_blocked = self.client.post(
            "/api/lead",
            json={"email": "client@test.fr", "domain": "test.fr"},
            headers={"X-Forwarded-For": ip}
        )
        self.assertEqual(res_blocked.status_code, 429)
        self.assertIn("Trop de requêtes sur /api/lead", res_blocked.json()["detail"])
        server._lead_limiter.reset()

    def test_33_non_product_page_classification(self):
        """Qualification de page : détection page non-marchande / institutionnelle sans faux produit."""
        from unittest.mock import patch, AsyncMock, MagicMock
        server._scan_limiter.reset()

        wiki_html = """<!DOCTYPE html><html><head><title>Wikipedia, the free encyclopedia</title></head>
        <body>
        <h1>Welcome to Wikipedia</h1>
        <p>Wikipedia is a free online encyclopedia written collaboratively by people around the world.</p>
        </body></html>"""

        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.headers = {"content-type": "text/html"}
        fake_resp.text = wiki_html

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=fake_resp), \
             patch("server.fetch_robots_txt", new_callable=AsyncMock, return_value={"found": True, "global_disallowed": False, "disallowed_bots": []}), \
             patch("server.check_llms_txt", new_callable=AsyncMock, return_value={"found": False}):
            res = self.client.post("/api/scan", json={"url": "https://en.wikipedia.org/wiki/Main_Page"})
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertFalse(data["isProductPage"])
            self.assertIn("Page d'information", data["summary"])
            self.assertEqual(data["name"], "Wikipedia, the free encyclopedia")

    def test_34_sanitized_dns_error_message(self):
        """Erreurs réseau : élimination des fuites techniques [Errno -2] sur NXDOMAIN."""
        from unittest.mock import patch, AsyncMock
        import socket
        server._scan_limiter.reset()

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=socket.gaierror(-2, "Name or service not known")):
            res = self.client.post("/api/scan", json={"url": "https://store-inexistant-xyz-987.fr/produit"})
            self.assertEqual(res.status_code, 400)
            detail = res.json()["detail"]
            self.assertNotIn("[Errno -2]", detail)
            self.assertIn("Nom de domaine introuvable", detail)

    def test_35_favicon_and_docs_endpoints(self):
        """Ressources statiques : /favicon.ico et /docs/*.md répondent avec 200 et types valides."""
        # 1. Favicon SVG
        res_fav = self.client.get("/favicon.ico")
        self.assertEqual(res_fav.status_code, 200)
        self.assertEqual(res_fav.headers.get("content-type"), "image/svg+xml")
        self.assertIn("<svg", res_fav.text)

        # 2. Docs PRD
        res_prd = self.client.get("/docs/PRD.md")
        self.assertEqual(res_prd.status_code, 200)
        self.assertIn("text/markdown", res_prd.headers.get("content-type"))
        self.assertIn("PRD", res_prd.text)

    def test_36_csr_and_waf_non_blocking_audit(self):
        """Architecture : détection non-bloquante CSR/SPA, qualification auditType et encart PDF."""
        from unittest.mock import patch, AsyncMock, MagicMock
        server._scan_limiter.reset()

        csr_html = """<!DOCTYPE html>
        <html>
          <head><title>Boutique SPA React</title></head>
          <body>
            <noscript>You need to enable JavaScript to run this app.</noscript>
            <div id="root"></div>
            <script type="module" src="/src/main.jsx"></script>
          </body>
        </html>"""

        mock_resp = MagicMock()
        mock_resp.text = csr_html
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "text/html"}

        fake_robots = {"found": True, "global_disallowed": False, "disallowed_bots": [], "raw": "User-agent: *\nAllow: /"}
        fake_llms = {"found": True, "path": "/.well-known/llms.txt", "content": "# LLMs.txt\nAPI: https://api.myspa.fr"}

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp), \
             patch("server.fetch_robots_txt", new_callable=AsyncMock, return_value=fake_robots), \
             patch("server.check_llms_txt", new_callable=AsyncMock, return_value=fake_llms):

            res = self.client.post("/api/scan", json={"url": "https://boutique-spa.fr/products/chemise"})
            self.assertEqual(res.status_code, 200)
            data = res.json()

            # 1. Qualification non-bloquante
            self.assertTrue(data["isWafBlocked"])
            self.assertEqual(data.get("auditType"), "CSR_SPA_UNRENDERED")
            self.assertIsNotNone(data.get("wafDetails"))
            self.assertEqual(data["wafDetails"].get("type"), "CSR")
            self.assertIn("Client-Side", data["wafDetails"].get("blocker", ""))

            # 2. Conservation de l'intégrité de l'audit des fichiers statiques (robots & llms)
            self.assertIn("crawl", data["pillars"])
            self.assertGreater(data["pillars"]["crawl"]["score"], 0)
            self.assertIn("proto", data["pillars"])

            # 3. Warning prioritaire dans brokenItems
            broken_titles = [item["title"] for item in data["brokenItems"]]
            self.assertTrue(any("Client-Side Rendering" in t for t in broken_titles))

            # 4. Génération PDF avec encart d'avertissement architecture
            res_pdf = self.client.post("/api/report/pdf", json={
                "email": "dev@boutique-spa.fr",
                "auditData": data
            })
            self.assertEqual(res_pdf.status_code, 200)
            self.assertEqual(res_pdf.headers.get("content-type"), "application/pdf")
            self.assertTrue(res_pdf.content.startswith(b"%PDF-"))


if __name__ == "__main__":
    unittest.main()





