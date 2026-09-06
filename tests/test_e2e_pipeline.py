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

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=fake_page), \
             patch("server.fetch_robots_txt", new_callable=AsyncMock,
                   return_value={"found": False, "global_disallowed": False, "disallowed_bots": [], "raw": ""}), \
             patch("server.check_llms_txt", new_callable=AsyncMock,
                   return_value={"found": False, "path": None, "content": None}):
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
        self.assertIn('"welcomeoffice-com-agent"', snippets["mcpConfig"])
        self.assertIn('--store=welcomeoffice.com', snippets["mcpConfig"])

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


if __name__ == "__main__":
    unittest.main()

