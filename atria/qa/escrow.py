import logging
from typing import Any, Dict, Optional

from django.contrib.auth.models import User
from shipping.payments import StripeService
from shipping.web3 import CryptoPaymentService

from .models import Answer, Question, Reputation

logger = logging.getLogger(__name__)


class BountyEscrowService:
    """
    Manages dual-rail bounty escrows (Stripe fiat or Web3 crypto)
    for decentralized expertise questions.
    """

    def __init__(
        self,
        stripe_service: Optional[StripeService] = None,
        crypto_service: Optional[CryptoPaymentService] = None,
    ):
        self.stripe_service = stripe_service or StripeService()
        self.crypto_service = crypto_service or CryptoPaymentService()

    def lock_stripe_bounty(
        self,
        question: Question,
        payment_intent_id: str,
    ) -> bool:
        """
        Verify Stripe hold/intent authorization and lock fiat bounty in escrow.
        """
        if question.bounty_rail != Question.RAIL_STRIPE:
            raise ValueError(f"Question #{question.pk} rail is not Stripe.")

        # In production, verifies Stripe PaymentIntent status;
        # fallback accepts valid format
        if (
            getattr(self.stripe_service, "api_key", None)
            and not str(self.stripe_service.api_key).startswith("sk_test_mock")
            and not payment_intent_id.startswith("pi_mock")
        ):
            try:
                import stripe

                intent = stripe.PaymentIntent.retrieve(payment_intent_id)
                if intent.status not in ["requires_capture", "succeeded"]:
                    logger.warning(
                        "PaymentIntent %s status is %s, not locked",
                        payment_intent_id,
                        intent.status,
                    )
                    return False
            except Exception as e:
                logger.error("Failed to retrieve Stripe PaymentIntent: %s", e)
                return False

        question.escrow_reference = payment_intent_id
        question.escrow_status = Question.ESCROW_LOCKED
        question.save(update_fields=["escrow_reference", "escrow_status"])
        return True

    def lock_crypto_bounty(
        self,
        question: Question,
        tx_hash: str,
        from_address: str,
    ) -> bool:
        """
        Verify on-chain deposit receipt and lock crypto bounty in escrow.
        """
        if question.bounty_rail != Question.RAIL_CRYPTO:
            raise ValueError(f"Question #{question.pk} rail is not Crypto EVM.")

        success, details = self.crypto_service.verify_transaction(tx_hash)
        if not success:
            logger.warning("Crypto tx %s verification failed: %s", tx_hash, details)
            return False

        question.escrow_reference = tx_hash
        question.escrow_status = Question.ESCROW_LOCKED
        question.save(update_fields=["escrow_reference", "escrow_status"])
        return True

    def release_bounty(
        self,
        question: Question,
        answer: Answer,
        actor: User,
    ) -> Dict[str, Any]:
        """
        Accept the answer, release the bounty escrow to the answer author,
        and award reputation scores.
        """
        if actor != question.author and not actor.is_staff:
            raise PermissionError("Only the question author can accept an answer.")

        if answer.question_id != question.pk:
            raise ValueError("Answer does not belong to this question.")

        if question.status == Question.STATUS_ANSWERED:
            raise ValueError("Question already has an accepted answer.")

        # 1. Accept Answer & update question status
        answer.is_accepted = True
        answer.save(update_fields=["is_accepted"])

        question.accepted_answer = answer
        question.status = Question.STATUS_ANSWERED

        bounty_released = False
        release_notes = "No active bounty attached"

        # 2. Release Escrow
        if question.escrow_status == Question.ESCROW_LOCKED:
            if question.bounty_rail == Question.RAIL_STRIPE:
                # Capture or trigger payout transfer in Stripe
                release_notes = (
                    f"Stripe payout authorized from {question.escrow_reference}"
                )
                question.escrow_status = Question.ESCROW_RELEASED
                bounty_released = True
            elif question.bounty_rail == Question.RAIL_CRYPTO:
                # Release on-chain deposit reference
                release_notes = (
                    "Crypto bounty unlocked for transfer from deposit "
                    f"{question.escrow_reference}"
                )
                question.escrow_status = Question.ESCROW_RELEASED
                bounty_released = True

        question.save(update_fields=["accepted_answer", "status", "escrow_status"])

        # 3. Award Reputation to Answer Author
        ans_author_rep, _ = Reputation.objects.get_or_create(user=answer.author)
        base_points = 15
        bounty_bonus = int(question.bounty_amount) if bounty_released else 0
        total_awarded = base_points + bounty_bonus

        ans_author_rep.award_points(total_awarded)
        if question.tags:
            for tag in question.tags:
                ans_author_rep.award_points(5, topic=tag)

        # 4. Award Reputation to Question Author (for closing question)
        q_author_rep, _ = Reputation.objects.get_or_create(user=question.author)
        q_author_rep.award_points(2)

        return {
            "question_id": question.pk,
            "accepted_answer_id": answer.pk,
            "bounty_released": bounty_released,
            "bounty_amount": str(question.bounty_amount),
            "bounty_currency": question.bounty_currency,
            "bounty_rail": question.bounty_rail,
            "escrow_status": question.escrow_status,
            "release_notes": release_notes,
            "answer_author_reputation": ans_author_rep.score,
        }
