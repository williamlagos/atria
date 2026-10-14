"""Integration tests for the unified Django Ninja API routers in Atria."""

import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase
from eth_account import Account
from eth_account.messages import encode_defunct
from feedly.models import Page
from shipping.models import Category, Order, Product


class AuthRouterTestCase(TestCase):
    def setUp(self):
        self.client = Client()

    def test_register_and_login(self):
        # Register
        res = self.client.post(
            "/api/v1/auth/register",
            data=json.dumps(
                {
                    "username": "satoshi",
                    "email": "satoshi@example.com",
                    "password": "strongpassword123",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["username"], "satoshi")
        self.assertTrue(data["is_authenticated"])

        # Check me
        me_res = self.client.get("/api/v1/auth/me")
        self.assertEqual(me_res.status_code, 200)
        self.assertEqual(me_res.json()["username"], "satoshi")

        # Logout
        logout_res = self.client.post("/api/v1/auth/logout")
        self.assertEqual(logout_res.status_code, 200)
        self.assertEqual(logout_res.json()["status"], "logged_out")

        # Login
        login_res = self.client.post(
            "/api/v1/auth/login",
            data=json.dumps({"username": "satoshi", "password": "strongpassword123"}),
            content_type="application/json",
        )
        self.assertEqual(login_res.status_code, 200)
        self.assertEqual(login_res.json()["username"], "satoshi")

    def test_register_duplicate_username(self):
        User.objects.create_user(username="taken", email="taken@example.com")
        res = self.client.post(
            "/api/v1/auth/register",
            data=json.dumps(
                {
                    "username": "taken",
                    "email": "new@example.com",
                    "password": "pwd",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)

    def test_siwe_nonce_and_verify(self):
        wallet = Account.create()
        address = wallet.address

        # Get nonce
        res_nonce = self.client.get(f"/api/v1/auth/siwe/nonce?address={address}")
        self.assertEqual(res_nonce.status_code, 200)
        nonce = res_nonce.json()["nonce"]
        self.assertTrue(nonce)

        # Build SIWE message
        siwe_message = (
            f"localhost wants you to sign in with your Ethereum account:\n"
            f"{address}\n\n"
            f"URI: http://localhost/login\n"
            f"Version: 1\n"
            f"Chain ID: 1\n"
            f"Nonce: {nonce}\n"
            f"Issued At: 2026-10-13T12:00:00Z"
        )
        signable_msg = encode_defunct(text=siwe_message)
        signed = wallet.sign_message(signable_msg)
        signature = signed.signature.hex()

        # Verify
        res_verify = self.client.post(
            "/api/v1/auth/siwe/verify",
            data=json.dumps(
                {
                    "message": siwe_message,
                    "signature": signature,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(res_verify.status_code, 200)
        verify_data = res_verify.json()
        self.assertTrue(verify_data["success"])
        self.assertEqual(verify_data["address"], address)

        # Check me is now logged in as this wallet user
        me_res = self.client.get("/api/v1/auth/me")
        self.assertEqual(me_res.status_code, 200)
        self.assertTrue(me_res.json()["is_authenticated"])


class SocialRouterTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.alice = User.objects.create_user(username="alice", email="a@ex.com")
        self.bob = User.objects.create_user(username="bob", email="b@ex.com")

    def test_actors_list_and_detail(self):
        res = self.client.get("/api/v1/social/actors")
        self.assertEqual(res.status_code, 200)

        res_alice = self.client.get("/api/v1/social/actors/alice")
        self.assertEqual(res_alice.status_code, 200)
        self.assertEqual(res_alice.json()["username"], "alice")

    def test_follow_and_unfollow(self):
        self.client.force_login(self.alice)

        # Follow Bob
        res = self.client.post(
            "/api/v1/social/follow",
            data=json.dumps({"target_username": "bob"}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["actor"], "alice")
        self.assertEqual(res.json()["target"], "bob")

        # Followers of bob
        res_followers = self.client.get("/api/v1/social/actors/bob/followers")
        self.assertEqual(res_followers.status_code, 200)
        self.assertEqual(len(res_followers.json()), 1)
        self.assertEqual(res_followers.json()[0]["username"], "alice")

        # Following of alice
        res_following = self.client.get("/api/v1/social/actors/alice/following")
        self.assertEqual(res_following.status_code, 200)
        self.assertEqual(len(res_following.json()), 1)

        # Unfollow
        res_unfollow = self.client.post(
            "/api/v1/social/unfollow",
            data=json.dumps({"target_username": "bob"}),
            content_type="application/json",
        )
        self.assertEqual(res_unfollow.status_code, 200)
        self.assertEqual(res_unfollow.json()["status"], "unfollowed")

    def test_activities_and_outbox(self):
        self.client.force_login(self.alice)
        res_act = self.client.post(
            "/api/v1/social/activities",
            data=json.dumps(
                {
                    "activity_type": "Create",
                    "object_type": "Note",
                    "content": "Hello ActivityPub fediverse!",
                    "summary": "First post",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(res_act.status_code, 200)
        self.assertEqual(res_act.json()["actor"], "alice")

        # Check outbox
        res_outbox = self.client.get("/api/v1/social/actors/alice/outbox")
        self.assertEqual(res_outbox.status_code, 200)
        self.assertGreaterEqual(len(res_outbox.json()), 1)


class ShopRouterTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="merchant", email="m@ex.com")
        self.category = Category.objects.create(name="Tech", slug="tech")
        self.product = Product.objects.create(
            name="Mechanical Keyboard",
            slug="mech-keyboard",
            price=Decimal("120.00"),
            sku="KB-001",
            creator=self.user,
            category=self.category,
        )

    def test_products_list_and_detail(self):
        res = self.client.get("/api/v1/shop/products")
        self.assertEqual(res.status_code, 200)
        self.assertGreaterEqual(len(res.json()), 1)

        res_detail = self.client.get(f"/api/v1/shop/products/{self.product.pk}")
        self.assertEqual(res_detail.status_code, 200)
        self.assertEqual(res_detail.json()["name"], "Mechanical Keyboard")

    def test_create_product(self):
        self.client.force_login(self.user)
        payload = {
            "name": "Wireless Mouse",
            "price": "55.00",
            "sku": "MS-002",
            "description": "Ergonomic mouse",
            "category_id": self.category.pk,
        }
        res = self.client.post(
            "/api/v1/shop/products",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["name"], "Wireless Mouse")

    def test_cart_and_order_flow(self):
        self.client.force_login(self.user)
        # Add to cart
        res_add = self.client.post(
            "/api/v1/shop/cart/items",
            data=json.dumps({"product_id": self.product.pk, "quantity": 2}),
            content_type="application/json",
        )
        self.assertEqual(res_add.status_code, 200)
        cart_data = res_add.json()
        self.assertEqual(len(cart_data["items"]), 1)
        self.assertEqual(cart_data["total"], "240.00")

        # Checkout
        res_order = self.client.post("/api/v1/shop/orders")
        self.assertEqual(res_order.status_code, 200)
        order_data = res_order.json()
        self.assertEqual(order_data["status"], Order.STATUS_PENDING)
        self.assertEqual(order_data["total"], "240.00")

        # List orders
        res_orders = self.client.get("/api/v1/shop/orders")
        self.assertEqual(res_orders.status_code, 200)
        self.assertEqual(len(res_orders.json()), 1)

    def test_creator_tiers(self):
        self.client.force_login(self.user)
        payload = {
            "name": "Gold Patron",
            "price": "15.00",
            "currency": "USD",
            "billing_frequency": "monthly",
            "description": "Full access",
            "perks": ["Discord role", "Early access"],
        }
        res = self.client.post(
            f"/api/v1/shop/creators/{self.user.pk}/tiers",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["name"], "Gold Patron")

        res_list = self.client.get(f"/api/v1/shop/creators/{self.user.pk}/tiers")
        self.assertEqual(res_list.status_code, 200)
        self.assertEqual(len(res_list.json()), 1)


class PaymentsRouterTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="patron", email="p@ex.com")
        self.creator = User.objects.create_user(username="artist", email="art@ex.com")
        self.order = Order.objects.create(
            user=self.user,
            total=Decimal("49.99"),
            status=Order.STATUS_PENDING,
        )

    @patch("shipping.payments.StripeService.create_checkout_session")
    def test_stripe_checkout(self, mock_checkout):
        mock_checkout.return_value = {
            "session_id": "cs_test_123",
            "url": "https://checkout.stripe.com/test",
        }
        payload = {
            "order_id": self.order.pk,
            "success_url": "https://example.com/success",
            "cancel_url": "https://example.com/cancel",
        }
        res = self.client.post(
            "/api/v1/payments/stripe/checkout",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["session_id"], "cs_test_123")

    @patch("shipping.payments.PayPalV2Service.create_order")
    def test_paypal_create_order(self, mock_paypal):
        mock_paypal.return_value = {
            "id": "PAYPAL-ORDER-123",
            "status": "CREATED",
            "links": [
                {"rel": "approve", "href": "https://paypal.com/checkout?token=123"}
            ],
        }
        payload = {
            "order_id": self.order.pk,
            "currency": "USD",
        }
        res = self.client.post(
            "/api/v1/payments/paypal/create-order",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["order_id"], "PAYPAL-ORDER-123")

    @patch("shipping.web3.CryptoPaymentService.verify_transaction")
    def test_crypto_verify(self, mock_verify):
        mock_verify.return_value = (
            True,
            {
                "tx_hash": "0xabc123",
                "from": "0x1111111111111111111111111111111111111111",
                "to": "0x2222222222222222222222222222222222222222",
                "value_wei": 1000000000000000000,
            },
        )
        payload = {
            "tx_hash": "0xabc123",
            "expected_to": "0x2222222222222222222222222222222222222222",
            "order_id": self.order.pk,
        }
        res = self.client.post(
            "/api/v1/payments/web3/verify",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["success"])
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_PAID)

    @patch("shipping.web3.ENSService.resolve_name")
    def test_ens_resolve(self, mock_resolve):
        mock_resolve.return_value = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
        res = self.client.get("/api/v1/payments/web3/ens/resolve?name=vitalik.eth")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            res.json()["result"], "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
        )

    def test_send_tip(self):
        self.client.force_login(self.user)
        payload = {
            "recipient_username": "artist",
            "amount": "25.00",
            "currency": "USD",
            "payment_rail": "stripe",
            "transaction_reference": "pi_tip_999",
            "message": "Keep up the great work!",
        }
        res = self.client.post(
            "/api/v1/payments/tip",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        tip_data = res.json()
        self.assertEqual(tip_data["recipient"], "artist")
        self.assertEqual(tip_data["amount"], "25.00")


class FeedsRouterTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="researcher", email="r@ex.com")
        self.page1 = Page.objects.create(
            name="Quantum Computing",
            content="Frontiers of quantum computing algorithms",
            user=self.user,
        )
        self.page2 = Page.objects.create(
            name="Web3 Protocols",
            content="Decentralized consensus mechanisms",
            user=self.user,
        )

    def test_chronological_and_trending_feeds(self):
        res_chrono = self.client.get("/api/v1/feeds/chronological")
        self.assertEqual(res_chrono.status_code, 200)
        self.assertGreaterEqual(len(res_chrono.json()), 2)

        res_trend = self.client.get("/api/v1/feeds/trending")
        self.assertEqual(res_trend.status_code, 200)
        self.assertGreaterEqual(len(res_trend.json()), 2)

    def test_personalized_feed_and_interests(self):
        self.client.force_login(self.user)
        # Update interests
        res_int = self.client.post(
            "/api/v1/feeds/interests",
            data=json.dumps({"topics": ["Quantum", "Physics"]}),
            content_type="application/json",
        )
        self.assertEqual(res_int.status_code, 200)
        self.assertIn("Quantum", res_int.json()["topics"])

        # Fetch personalized feed
        res_pers = self.client.get("/api/v1/feeds/personalized")
        self.assertEqual(res_pers.status_code, 200)
        self.assertGreaterEqual(len(res_pers.json()), 2)

    def test_semantic_search(self):
        # Index pages with embeddings
        from feedly.ai import GeminiEmbeddingService

        embedder = GeminiEmbeddingService()
        embedder.embed_object(self.page1)
        embedder.embed_object(self.page2)

        res = self.client.post(
            "/api/v1/feeds/search",
            data=json.dumps({"query": "quantum computing qubits", "limit": 5}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        results = res.json()
        self.assertGreaterEqual(len(results), 1)

    def test_moderate_content(self):
        # Safe
        res_safe = self.client.post(
            "/api/v1/feeds/moderate",
            data=json.dumps({"content": "Welcome to our collaborative network"}),
            content_type="application/json",
        )
        self.assertEqual(res_safe.status_code, 200)
        self.assertEqual(res_safe.json()["status"], "approved")

        # Spam
        res_spam = self.client.post(
            "/api/v1/feeds/moderate",
            data=json.dumps(
                {"content": "Claim your airdrop at http://scam double your bitcoin"}
            ),
            content_type="application/json",
        )
        self.assertEqual(res_spam.status_code, 200)
        self.assertIn(res_spam.json()["status"], ["flagged", "rejected"])
