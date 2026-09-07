import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from bs4 import BeautifulSoup
from starlette.testclient import TestClient
from server import app, extract_json_ld, analyze_schema, extract_best_product_image

class TestImageExtraction(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_schema_content_url(self):
        html = '''
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Parka Imperméable Hiver",
          "image": {
            "@type": "ImageObject",
            "contentUrl": "https://brand.com/images/parka-hd.jpg"
          }
        }
        </script>
        '''
        soup = BeautifulSoup(html, "html.parser")
        json_ld = extract_json_ld(soup)
        schema_res = analyze_schema(json_ld)
        best_img = extract_best_product_image(soup, "https://brand.com", schema_res["product_data"]["image"])
        self.assertEqual(best_img, "https://brand.com/images/parka-hd.jpg")

    def test_schema_graph_id_reference(self):
        html = '''
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@graph": [
            {
              "@type": "Product",
              "@id": "https://brand.com/#product",
              "name": "Chaussures Running Pro",
              "image": { "@id": "https://brand.com/#primaryimage" }
            },
            {
              "@type": "ImageObject",
              "@id": "https://brand.com/#primaryimage",
              "url": "https://brand.com/wp-content/uploads/running-pro.jpg"
            }
          ]
        }
        </script>
        '''
        soup = BeautifulSoup(html, "html.parser")
        json_ld = extract_json_ld(soup)
        schema_res = analyze_schema(json_ld)
        best_img = extract_best_product_image(soup, "https://brand.com", schema_res["product_data"]["image"])
        self.assertEqual(best_img, "https://brand.com/wp-content/uploads/running-pro.jpg")

    def test_schema_cdata_wrapper(self):
        html = '''
        <script type="application/ld+json">
        //<![CDATA[
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Sweat Capuche Bio",
          "image": "https://brand.com/images/sweat-bio.jpg"
        }
        //]]>
        </script>
        '''
        soup = BeautifulSoup(html, "html.parser")
        json_ld = extract_json_ld(soup)
        self.assertEqual(len(json_ld), 1)
        schema_res = analyze_schema(json_ld)
        self.assertEqual(schema_res["product_data"]["image"], "https://brand.com/images/sweat-bio.jpg")

    def test_dom_lazy_load_with_data_placeholder(self):
        html = '''
        <html>
          <head><title>Montre Connectée Sport - Marque X</title></head>
          <body>
            <h1>Montre Connectée Sport</h1>
            <img class="logo" src="https://brand.com/logo.svg">
            <img class="product-gallery-image"
                 src="data:image/svg+xml;base64,PHN2Zy..."
                 data-src="https://brand.com/uploads/montre-sport-large.jpg"
                 alt="Montre Connectée Sport Noir">
          </body>
        </html>
        '''
        soup = BeautifulSoup(html, "html.parser")
        img = extract_best_product_image(soup, "https://brand.com", None)
        self.assertEqual(img, "https://brand.com/uploads/montre-sport-large.jpg")

    def test_dom_woocommerce_large_image_with_blank_gif(self):
        html = '''
        <html>
          <head><title>Casque Audio Studio - Boutique</title></head>
          <body>
            <h1>Casque Audio Studio</h1>
            <img class="wp-post-image product-main"
                 src="https://brand.com/assets/blank.gif"
                 data-large_image="https://brand.com/wp-content/uploads/casque-studio-zoom.jpg"
                 alt="Casque Audio Studio">
          </body>
        </html>
        '''
        soup = BeautifulSoup(html, "html.parser")
        img = extract_best_product_image(soup, "https://brand.com", None)
        self.assertEqual(img, "https://brand.com/wp-content/uploads/casque-studio-zoom.jpg")

    def test_microdata_itemprop_image(self):
        html = '''
        <html>
          <head><title>Sac à Dos Urbain</title></head>
          <body>
            <h1>Sac à Dos Urbain</h1>
            <img itemprop="image" src="https://brand.com/images/sac-urbain.jpg" alt="Sac à dos urbain">
          </body>
        </html>
        '''
        soup = BeautifulSoup(html, "html.parser")
        img = extract_best_product_image(soup, "https://brand.com", None)
        self.assertEqual(img, "https://brand.com/images/sac-urbain.jpg")

    def test_proxy_endpoint_security(self):
        # Invalid URL
        r1 = self.client.get("/api/proxy-image?url=not_a_url")
        self.assertEqual(r1.status_code, 400)

        # SSRF forbidden
        r2 = self.client.get("/api/proxy-image?url=http://127.0.0.1:8000/server.py")
        self.assertEqual(r2.status_code, 403)

if __name__ == '__main__':
    unittest.main()
