import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase
from feedly.ai import GeminiEmbeddingService
from feedly.models import Page
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


class AIFeedAndDiscoveryEndpointsTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ai_researcher", email="ai@atria.local", password="password123"
        )
        self.page1 = Page.objects.create(
            name="!#Decentralized AI",
            content="Federated models and local edge inference techniques.",
            user=self.user,
        )
        self.page2 = Page.objects.create(
            name="!#Urban Gardening",
            content="Hydroponics and balcony vegetable gardening tips.",
            user=self.user,
        )
        embedding_service = GeminiEmbeddingService()
        embedding_service.embed_object(self.page1)
        embedding_service.embed_object(self.page2)

    def test_chronological_and_trending_feed_endpoints(self):
        res_chrono = self.client.get("/feeds/chronological/")
        self.assertEqual(res_chrono.status_code, 200)
        data_chrono = res_chrono.json()
        self.assertEqual(data_chrono["strategy"], "chronological")
        self.assertGreaterEqual(data_chrono["count"], 2)

        res_trending = self.client.get("/feeds/trending/")
        self.assertEqual(res_trending.status_code, 200)
        data_trending = res_trending.json()
        self.assertEqual(data_trending["strategy"], "trending")

    def test_semantic_search_endpoint(self):
        payload = {"query": "Machine learning and AI models", "top_k": 3}
        res = self.client.post(
            "/feeds/search/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("results", data)
        self.assertGreaterEqual(len(data["results"]), 1)
        top_match = data["results"][0]
        self.assertEqual(top_match["item"]["name"], "Decentralized AI")

    def test_content_moderation_endpoint(self):
        # Safe text
        safe_payload = {"text": "Great updates on decentralized networks!"}
        res_safe = self.client.post(
            "/feeds/moderate/",
            data=json.dumps(safe_payload),
            content_type="application/json",
        )
        self.assertEqual(res_safe.status_code, 200)
        self.assertEqual(res_safe.json()["status"], "approved")

        # Spam/scam text
        spam_payload = {
            "text": "Claim your airdrop at http://scam.xyz double your bitcoin"
        }
        res_spam = self.client.post(
            "/feeds/moderate/",
            data=json.dumps(spam_payload),
            content_type="application/json",
        )
        self.assertEqual(res_spam.status_code, 200)
        self.assertIn(res_spam.json()["status"], ["flagged", "rejected"])

    def test_personalized_feed_and_interests_endpoint(self):
        self.client.force_login(self.user)
        # Update user topics
        interest_payload = {"topics": ["Artificial Intelligence", "Neural Networks"]}
        res_interest = self.client.post(
            "/feeds/interests/",
            data=json.dumps(interest_payload),
            content_type="application/json",
        )
        self.assertEqual(res_interest.status_code, 200)
        self.assertTrue(res_interest.json()["has_vector"])

        # Fetch personalized feed
        res_feed = self.client.get("/feeds/personalized/")
        self.assertEqual(res_feed.status_code, 200)
        data_feed = res_feed.json()
        self.assertEqual(data_feed["strategy"], "personalized")
        self.assertGreaterEqual(len(data_feed["feed"]), 2)
        # The AI page should be ranked first due to semantic topic affinity
        self.assertEqual(data_feed["feed"][0]["item"]["name"], "Decentralized AI")
