from django.test import Client, TestCase


class CoreEndpointsTestCase(TestCase):
    def setUp(self):
        self.client = Client()

    def test_root_health_check(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "ok")

    def test_ninja_api_health(self):
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "ok")
        self.assertEqual(data.get("platform"), "atria")

    def test_ninja_api_system_info(self):
        response = self.client.get("/api/v1/system/info")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("name"), "Atria")
        self.assertEqual(data.get("federation_protocol"), "ActivityPub")

    def test_ninja_api_openapi_docs(self):
        response = self.client.get("/api/v1/docs")
        self.assertEqual(response.status_code, 200)

    def test_shop_endpoints(self):
        # Deliveries root
        self.assertEqual(self.client.get("/shop/").status_code, 200)
        # Products list
        products_res = self.client.get("/shop/products/")
        self.assertEqual(products_res.status_code, 200)
        self.assertIn("products", products_res.json())
        # Cart view
        cart_res = self.client.get("/shop/cart/")
        self.assertEqual(cart_res.status_code, 200)
        self.assertIn("items", cart_res.json())

    def test_socialize_webfinger_endpoint(self):
        # WebFinger requires a resource query parameter
        response = self.client.get("/.well-known/webfinger")
        self.assertEqual(response.status_code, 400)
