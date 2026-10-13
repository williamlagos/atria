import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase

from .escrow import BountyEscrowService
from .models import Answer, AnswerVote, Question, Reputation
from .services import QAService


class QAModelsAndReputationTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="password123")
        self.solver = User.objects.create_user(username="bob", password="password123")

    def test_reputation_badges_and_scoring(self):
        rep, _ = Reputation.objects.get_or_create(user=self.solver)
        self.assertEqual(rep.score, 100)
        self.assertEqual(rep.badges, [])

        # Award points
        rep.award_points(150, topic="python")
        self.assertEqual(rep.score, 250)
        self.assertIn("Contributor", rep.badges)
        self.assertIn("Python Specialist", rep.badges)

        rep.award_points(300)
        self.assertEqual(rep.score, 550)
        self.assertIn("Scholar", rep.badges)

    def test_question_and_answer_creation(self):
        q = Question.objects.create(
            title="How to optimize postgres queries?",
            description="Looking for tips on explain analyze.",
            author=self.user,
            tags=["postgres", "database"],
            bounty_amount=Decimal("50.00"),
            bounty_rail=Question.RAIL_STRIPE,
        )
        self.assertEqual(q.status, Question.STATUS_OPEN)
        self.assertFalse(q.is_bounty_active())

        a = Answer.objects.create(
            question=q,
            author=self.solver,
            content="Use indexes on foreign keys and vacuum regularly.",
            upvotes=5,
            downvotes=1,
        )
        self.assertEqual(a.score, 4)
        self.assertEqual(str(a), f"A#{a.pk} for Q#{q.pk} by bob")


class BountyEscrowServiceTestCase(TestCase):
    def setUp(self):
        self.asker = User.objects.create_user(username="asker", password="password123")
        self.answerer = User.objects.create_user(
            username="answerer", password="password123"
        )
        self.stranger = User.objects.create_user(
            username="stranger", password="password123"
        )

        self.question_stripe = Question.objects.create(
            title="Need help with Celery Beat",
            description="How to schedule recurring tasks in Docker?",
            author=self.asker,
            tags=["celery", "python"],
            bounty_amount=Decimal("25.00"),
            bounty_rail=Question.RAIL_STRIPE,
        )

        self.answer = Answer.objects.create(
            question=self.question_stripe,
            author=self.answerer,
            content="Use django-celery-beat and store schedules in the DB.",
        )

    def test_lock_stripe_bounty(self):
        service = BountyEscrowService()
        success = service.lock_stripe_bounty(self.question_stripe, "pi_mock_12345")
        self.assertTrue(success)
        self.question_stripe.refresh_from_db()
        self.assertEqual(self.question_stripe.escrow_status, Question.ESCROW_LOCKED)
        self.assertEqual(self.question_stripe.escrow_reference, "pi_mock_12345")
        self.assertTrue(self.question_stripe.is_bounty_active())

    @patch("shipping.web3.CryptoPaymentService.verify_transaction")
    def test_lock_crypto_bounty(self, mock_verify):
        mock_verify.return_value = (True, {"status": "confirmed", "value_wei": 10**17})
        q_crypto = Question.objects.create(
            title="Solidity reentrancy question",
            description="How does Checks-Effects-Interactions prevent reentrancy?",
            author=self.asker,
            bounty_amount=Decimal("0.1000"),
            bounty_rail=Question.RAIL_CRYPTO,
            bounty_currency="ETH",
        )
        tx = "0xabcdef1234567890abcdef1234567890" "abcdef1234567890abcdef1234567890"
        service = BountyEscrowService()
        success = service.lock_crypto_bounty(
            q_crypto,
            tx_hash=tx,
            from_address="0x1111111111111111111111111111111111111111",
        )
        self.assertTrue(success)
        q_crypto.refresh_from_db()
        self.assertEqual(q_crypto.escrow_status, Question.ESCROW_LOCKED)

    def test_release_bounty_permissions_and_reputation(self):
        service = BountyEscrowService()
        service.lock_stripe_bounty(self.question_stripe, "pi_mock_999")

        # Stranger cannot accept
        with self.assertRaises(PermissionError):
            service.release_bounty(self.question_stripe, self.answer, self.stranger)

        # Asker accepts answer
        result = service.release_bounty(self.question_stripe, self.answer, self.asker)
        self.assertTrue(result["bounty_released"])
        self.assertEqual(result["escrow_status"], Question.ESCROW_RELEASED)

        self.question_stripe.refresh_from_db()
        self.assertEqual(self.question_stripe.status, Question.STATUS_ANSWERED)
        self.assertEqual(self.question_stripe.accepted_answer, self.answer)

        # Verify reputation: base(15) + bounty(25) + topics(10) + starting(100) = 150
        ans_rep = Reputation.objects.get(user=self.answerer)
        self.assertGreaterEqual(ans_rep.score, 140)

        # Cannot accept again
        with self.assertRaises(ValueError):
            service.release_bounty(self.question_stripe, self.answer, self.asker)


class QAServiceTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="author", password="password")
        self.peer = User.objects.create_user(username="peer", password="password")
        self.service = QAService()

    def test_create_question_and_embedding(self):
        q = self.service.create_question(
            title="How to build ActivityPub in Django?",
            description="Implementing WebFinger and inbox delivery.",
            author=self.user,
            tags=["activitypub", "django"],
        )
        self.assertIsNotNone(q.pk)
        self.assertEqual(q.status, Question.STATUS_OPEN)

    def test_create_toxic_question_rejected(self):
        with self.assertRaises(ValueError):
            self.service.create_question(
                title="You idiot scam artist",
                description="I hate you moron fraudster",
                author=self.user,
            )

    def test_vote_answer(self):
        q = self.service.create_question(
            title="Django QuerySet optimization",
            description="Tips for prefetch_related vs select_related",
            author=self.user,
            tags=["django"],
        )
        a = self.service.create_answer(
            q, "Use select_related for single objects and prefetch for m2m", self.peer
        )

        # Peer cannot vote on self
        with self.assertRaises(PermissionError):
            self.service.vote_answer(a, self.peer, AnswerVote.VOTE_UP)

        # Upvote from author
        res_up = self.service.vote_answer(a, self.user, AnswerVote.VOTE_UP)
        self.assertEqual(res_up["upvotes"], 1)
        self.assertEqual(res_up["score"], 1)

        # Cancel upvote
        res_cancel = self.service.vote_answer(a, self.user, AnswerVote.VOTE_UP)
        self.assertEqual(res_cancel["upvotes"], 0)
        self.assertEqual(res_cancel["score"], 0)

    def test_related_questions(self):
        q1 = self.service.create_question(
            title="Deep Learning with PyTorch",
            description="How to build convolutional neural networks",
            author=self.user,
            tags=["ai", "pytorch"],
        )
        q2 = self.service.create_question(
            title="PyTorch vs TensorFlow for Deep Learning",
            description="Comparison of neural network frameworks",
            author=self.peer,
            tags=["ai", "pytorch"],
        )

        related = self.service.get_related_questions(q1)
        self.assertGreaterEqual(len(related), 1)
        self.assertEqual(related[0]["id"], q2.pk)


class QANinjaApiTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.author = User.objects.create_user(
            username="alice_dev", password="password123"
        )
        self.solver = User.objects.create_user(
            username="bob_expert", password="password123"
        )

        self.service = QAService()
        self.question = self.service.create_question(
            title="How to configure Redis with Celery in Django?",
            description="Setting up docker compose broker and backend URLs.",
            author=self.author,
            tags=["redis", "celery", "django"],
            bounty_amount=Decimal("10.00"),
            bounty_rail=Question.RAIL_STRIPE,
            escrow_reference="pi_mock_active",
        )

    def test_list_and_filter_questions(self):
        res = self.client.get("/api/v1/qa/questions")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["title"], self.question.title)

        # Filter by status
        res_open = self.client.get("/api/v1/qa/questions?status=open")
        self.assertEqual(res_open.status_code, 200)
        self.assertEqual(len(res_open.json()), 1)

        res_closed = self.client.get("/api/v1/qa/questions?status=closed")
        self.assertEqual(res_closed.status_code, 200)
        self.assertEqual(len(res_closed.json()), 0)

    def test_create_question_endpoint(self):
        self.client.force_login(self.author)
        payload = {
            "title": "What is Sign-In With Ethereum (SIWE)?",
            "description": "Explaining EIP-4361 authentication nonces.",
            "tags": ["web3", "ethereum"],
            "bounty_amount": "0.05",
            "bounty_rail": "crypto_evm",
            "bounty_currency": "ETH",
        }
        res = self.client.post(
            "/api/v1/qa/questions",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["title"], payload["title"])
        self.assertEqual(data["bounty_rail"], "crypto_evm")

    def test_question_detail_and_answer_submission(self):
        # 1. Detail before answers
        res_detail = self.client.get(f"/api/v1/qa/questions/{self.question.pk}")
        self.assertEqual(res_detail.status_code, 200)
        self.assertEqual(res_detail.json()["question"]["views_count"], 1)

        # 2. Submit answer
        self.client.force_login(self.solver)
        ans_payload = {
            "content": (
                "Configure CELERY_BROKER_URL=redis://localhost:6379/0 in settings."
            ),
        }
        res_ans = self.client.post(
            f"/api/v1/qa/questions/{self.question.pk}/answers",
            data=json.dumps(ans_payload),
            content_type="application/json",
        )
        self.assertEqual(res_ans.status_code, 201)
        ans_id = res_ans.json()["id"]

        # 3. Vote on answer
        self.client.force_login(self.author)
        res_vote = self.client.post(
            f"/api/v1/qa/answers/{ans_id}/vote",
            data=json.dumps({"vote_type": 1}),
            content_type="application/json",
        )
        self.assertEqual(res_vote.status_code, 200)
        self.assertEqual(res_vote.json()["score"], 1)

        # 4. Accept answer and release bounty
        res_accept = self.client.post(
            f"/api/v1/qa/questions/{self.question.pk}/accept/{ans_id}",
            content_type="application/json",
        )
        self.assertEqual(res_accept.status_code, 200)
        self.assertTrue(res_accept.json()["bounty_released"])

    def test_reputation_endpoint(self):
        res = self.client.get(f"/api/v1/qa/reputation/{self.author.username}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["username"], self.author.username)
        self.assertGreaterEqual(data["score"], 100)


class QAFederationTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="fed_author", password="password")
        self.question = Question.objects.create(
            title="Federated Question",
            description="Can ActivityPub federate questions across instances?",
            author=self.user,
            tags=["fediverse", "activitypub"],
            bounty_amount=Decimal("15.00"),
            bounty_rail=Question.RAIL_STRIPE,
        )
        self.answer = Answer.objects.create(
            question=self.question,
            author=self.user,
            content="Yes, using Question and Note types.",
        )

    def test_question_federation_jsonld(self):
        res = self.client.get(f"/qa/questions/{self.question.pk}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "application/activity+json")
        data = res.json()
        self.assertEqual(data["type"], "Question")
        self.assertEqual(data["name"], self.question.title)
        self.assertIn("atria:bounty", data)

    def test_answer_federation_jsonld(self):
        res = self.client.get(f"/qa/answers/{self.answer.pk}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "application/activity+json")
        data = res.json()
        self.assertEqual(data["type"], "Note")
        self.assertEqual(data["content"], self.answer.content)
        self.assertIn(str(self.question.pk), data["inReplyTo"])
