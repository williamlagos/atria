"""Unified Payments Router for Atria (Stripe, PayPal v2, and Web3 EVM / ENS)."""

from decimal import Decimal
from typing import Any, Dict, Optional

from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from ninja import Router, Schema
from ninja.errors import HttpError
from shipping.models import CryptoPayment, Order, Tip
from shipping.payments import PayPalV2Service, StripeService
from shipping.web3 import CryptoPaymentService, ENSService

payments_router = Router()


class StripeCheckoutIn(Schema):
    order_id: int
    success_url: str
    cancel_url: str


class StripeCheckoutOut(Schema):
    session_id: str
    url: str


class PaymentIntentIn(Schema):
    amount: str
    currency: str = "usd"
    metadata: Dict[str, Any] = {}


class PaymentIntentOut(Schema):
    id: str
    client_secret: str


class PayPalCreateOrderIn(Schema):
    order_id: int
    currency: str = "USD"
    return_url: Optional[str] = None
    cancel_url: Optional[str] = None


class PayPalCreateOrderOut(Schema):
    order_id: str
    status: str
    approve_url: Optional[str] = None


class PayPalCaptureIn(Schema):
    paypal_order_id: str


class PayPalCaptureOut(Schema):
    status: str
    capture_id: Optional[str] = None


class CryptoVerifyIn(Schema):
    tx_hash: str
    expected_to: str
    expected_amount_wei: Optional[int] = None
    order_id: Optional[int] = None


class CryptoVerifyOut(Schema):
    success: bool
    details: Dict[str, Any]


class ENSResolveOut(Schema):
    query: str
    result: Optional[str] = None


class TipIn(Schema):
    recipient_username: str
    amount: str
    currency: str = "USD"
    payment_rail: str = "stripe"
    transaction_reference: str
    message: str = ""


class TipOut(Schema):
    id: int
    sender: Optional[str] = None
    recipient: str
    amount: str
    currency: str
    payment_rail: str
    transaction_reference: str
    message: str


@payments_router.post("/stripe/checkout", response=StripeCheckoutOut)
def create_stripe_checkout(request, payload: StripeCheckoutIn):
    """Creates a hosted Stripe Checkout session for an Order."""
    order = get_object_or_404(Order, pk=payload.order_id)
    stripe_service = StripeService()
    try:
        session_data = stripe_service.create_checkout_session(
            order=order,
            success_url=payload.success_url,
            cancel_url=payload.cancel_url,
            customer_email=(
                request.user.email if request.user.is_authenticated else None
            ),
        )
        return {
            "session_id": session_data["session_id"],
            "url": session_data["url"],
        }
    except Exception as e:
        raise HttpError(400, f"Stripe Checkout creation failed: {str(e)}")


@payments_router.post("/stripe/payment-intent", response=PaymentIntentOut)
def create_payment_intent(request, payload: PaymentIntentIn):
    """Creates a custom Stripe PaymentIntent for tips, bounties, or direct charges."""
    stripe_service = StripeService()
    try:
        intent = stripe_service.create_payment_intent(
            amount=Decimal(payload.amount),
            currency=payload.currency,
            metadata=payload.metadata,
        )
        return {
            "id": intent.get("id", ""),
            "client_secret": intent.get("client_secret", ""),
        }
    except Exception as e:
        raise HttpError(400, f"PaymentIntent creation failed: {str(e)}")


@payments_router.post("/paypal/create-order", response=PayPalCreateOrderOut)
def create_paypal_order(request, payload: PayPalCreateOrderIn):
    """Creates an order via modern PayPal v2 Orders REST API."""
    order = get_object_or_404(Order, pk=payload.order_id)
    paypal_service = PayPalV2Service()
    try:
        data = paypal_service.create_order(
            amount=order.total,
            currency=payload.currency,
            custom_id=str(order.pk),
            return_url=payload.return_url,
            cancel_url=payload.cancel_url,
        )
        approve_url = None
        for link in data.get("links", []):
            if link.get("rel") == "approve":
                approve_url = link.get("href")
                break

        return {
            "order_id": data.get("id", ""),
            "status": data.get("status", "CREATED"),
            "approve_url": approve_url,
        }
    except Exception as e:
        raise HttpError(400, f"PayPal Order creation failed: {str(e)}")


@payments_router.post("/paypal/capture-order", response=PayPalCaptureOut)
def capture_paypal_order(request, payload: PayPalCaptureIn):
    """Captures an approved PayPal v2 order."""
    paypal_service = PayPalV2Service()
    try:
        data = paypal_service.capture_order(payload.paypal_order_id)
        capture_id = None
        units = data.get("purchase_units", [])
        if units:
            payments = units[0].get("payments", {})
            captures = payments.get("captures", [])
            if captures:
                capture_id = captures[0].get("id")

        return {
            "status": data.get("status", "COMPLETED"),
            "capture_id": capture_id,
        }
    except Exception as e:
        raise HttpError(400, f"PayPal Order capture failed: {str(e)}")


@payments_router.post("/web3/verify", response=CryptoVerifyOut)
def verify_crypto_payment(request, payload: CryptoVerifyIn):
    """Verifies on-chain EVM transactions for orders, bounties, or tips."""
    service = CryptoPaymentService()
    success, details_or_error = service.verify_transaction(
        tx_hash=payload.tx_hash,
        expected_to=payload.expected_to,
        expected_amount_wei=payload.expected_amount_wei,
    )

    if not success:
        return {
            "success": False,
            "details": {"error": str(details_or_error)},
        }

    order = None
    if payload.order_id:
        order = Order.objects.filter(pk=payload.order_id).first()
        if order:
            order.status = Order.STATUS_PAID
            order.save(update_fields=["status"])

    details = details_or_error if isinstance(details_or_error, dict) else {}
    CryptoPayment.objects.update_or_create(
        tx_hash=payload.tx_hash,
        defaults={
            "order": order,
            "from_address": details.get("from", ""),
            "to_address": details.get("to", payload.expected_to),
            "amount_wei": Decimal(str(details.get("value_wei", 0))),
            "status": CryptoPayment.STATUS_CONFIRMED,
        },
    )

    return {
        "success": True,
        "details": details,
    }


@payments_router.get("/web3/ens/resolve", response=ENSResolveOut)
def resolve_ens(request, name: Optional[str] = None, address: Optional[str] = None):
    """Resolves ENS names forward (name.eth -> 0x...) or reverse (0x... -> name.eth)."""
    service = ENSService()
    if name:
        resolved = service.resolve_name(name)
        return {"query": name, "result": resolved}
    elif address:
        resolved = service.reverse_resolve(address)
        return {"query": address, "result": resolved}
    raise HttpError(400, "Provide either 'name' or 'address' to resolve")


@payments_router.post("/tip", response=TipOut)
def send_tip(request, payload: TipIn):
    """Records a creator tip across Web2 or Web3 rails."""
    recipient = get_object_or_404(User, username=payload.recipient_username)
    sender = request.user if request.user.is_authenticated else None

    tip = Tip.objects.create(
        sender=sender,
        recipient=recipient,
        amount=Decimal(payload.amount),
        currency=payload.currency,
        payment_rail=payload.payment_rail,
        transaction_reference=payload.transaction_reference,
        message=payload.message,
    )

    return {
        "id": tip.pk,
        "sender": sender.username if sender else None,
        "recipient": recipient.username,
        "amount": str(tip.amount),
        "currency": tip.currency,
        "payment_rail": tip.payment_rail,
        "transaction_reference": tip.transaction_reference,
        "message": tip.message,
    }
