import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase
from socialize.services import ActorService


class CoreEndpointsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.actor_service = ActorService()

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


class ActivityPubFederationEndpointsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.actor_service = ActorService()
        self.user = User.objects.create_user(username="federated_user")
        self.actor = self.actor_service.create_actor({"username": "federated_user"})

    def test_webfinger_resolution(self):
        response = self.client.get(
            "/.well-known/webfinger?resource=acct:federated_user@localhost:8000"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("subject"), "acct:federated_user@localhost:8000")
        self.assertTrue(
            any(link.get("rel") == "self" for link in data.get("links", []))
        )

    def test_actor_activitypub_representation(self):
        response = self.client.get("/users/federated_user/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("type"), "Person")
        self.assertEqual(data.get("preferredUsername"), "federated_user")
        self.assertIn("publicKey", data)
        self.assertEqual(data["publicKey"]["owner"], self.actor.get_actor_url())

    def test_nodeinfo_endpoints(self):
        # Discovery endpoint
        disc_res = self.client.get("/.well-known/nodeinfo")
        self.assertEqual(disc_res.status_code, 200)
        disc_data = disc_res.json()
        self.assertTrue(len(disc_data.get("links", [])) > 0)

        # NodeInfo 2.0 schema endpoint
        schema_res = self.client.get("/nodeinfo/2.0")
        self.assertEqual(schema_res.status_code, 200)
        schema_data = schema_res.json()
        self.assertEqual(schema_data.get("version"), "2.0")
        self.assertIn("activitypub", schema_data.get("protocols", []))

    def test_collections_and_outbox(self):
        # Followers collection
        followers_res = self.client.get("/users/federated_user/followers/")
        self.assertEqual(followers_res.status_code, 200)
        self.assertEqual(followers_res.json().get("type"), "OrderedCollection")

        # Following collection
        following_res = self.client.get("/users/federated_user/following/")
        self.assertEqual(following_res.status_code, 200)
        self.assertEqual(following_res.json().get("type"), "OrderedCollection")

        # Outbox collection
        outbox_res = self.client.get("/users/federated_user/outbox/")
        self.assertEqual(outbox_res.status_code, 200)
        self.assertEqual(outbox_res.json().get("type"), "OrderedCollection")

    @patch("socialize.tasks.process_inbound_activity_task.delay")
    def test_inbox_activity_acceptance(self, mock_task):
        payload = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Like",
            "actor": "https://remote.social/users/bob",
            "object": "https://localhost:8000/users/federated_user/",
        }
        response = self.client.post(
            "/inbox/",
            data=json.dumps(payload),
            content_type="application/activity+json",
        )
        self.assertEqual(response.status_code, 202)
        mock_task.assert_called_once()


class CommerceAndPaymentsEndpointsTestCase(TestCase):
    def setUp(self):
        from decimal import Decimal

        from shipping.models import Order, Product

        self.client = Client()
        self.creator = User.objects.create_user(username="creator_carol")
        self.fan = User.objects.create_user(username="fan_dave")
        self.product = Product.objects.create(
            name="Digital Course",
            slug="digital-course",
            price=Decimal("49.99"),
            sku="DC-001",
            creator=self.creator,
        )
        self.order = Order.objects.create(user=self.fan, total=Decimal("49.99"))

    def test_siwe_nonce_flow(self):
        address = "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed"
        response = self.client.get(f"/shop/web3/siwe/nonce/?address={address}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["address"], address)
        self.assertIn("nonce", data)

    def test_creator_tiers_and_tip_endpoints(self):
        # Create a tier
        self.client.force_login(self.creator)
        tier_payload = {
            "name": "Supporter",
            "price": "5.00",
            "currency": "USD",
            "perks": ["Badge", "Shoutout"],
        }
        res_tier = self.client.post(
            f"/shop/creators/{self.creator.pk}/tiers/",
            data=json.dumps(tier_payload),
            content_type="application/json",
        )
        self.assertEqual(res_tier.status_code, 201)

        # Send a tip
        tip_payload = {
            "amount": "15.00",
            "currency": "USD",
            "payment_rail": "stripe",
            "message": "Awesome work!",
        }
        res_tip = self.client.post(
            f"/shop/creators/{self.creator.pk}/tip/",
            data=json.dumps(tip_payload),
            content_type="application/json",
        )
        self.assertEqual(res_tip.status_code, 201)
        self.assertEqual(res_tip.json()["amount"], "15.00")

    @patch("shipping.payments.StripeService.create_checkout_session")
    def test_stripe_checkout_endpoint(self, mock_checkout):
        mock_checkout.return_value = {
            "session_id": "cs_mock_123",
            "url": "https://checkout.stripe.com/pay/cs_mock_123",
        }
        self.client.force_login(self.fan)
        payload = {"order_id": self.order.pk}
        response = self.client.post(
            "/shop/payments/stripe/checkout/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["session_id"], "cs_mock_123")

    @patch("shipping.payments.PayPalV2Service.create_order")
    def test_paypal_create_order_endpoint(self, mock_paypal):
        mock_paypal.return_value = {
            "id": "PAYPAL-ORDER-123",
            "status": "CREATED",
        }
        self.client.force_login(self.fan)
        payload = {"order_id": self.order.pk}
        response = self.client.post(
            "/shop/payments/paypal/create-order/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], "PAYPAL-ORDER-123")
