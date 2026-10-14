"""Authentication and Identity router for Atria (Standard Django + SIWE)."""

from typing import Optional

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from ninja import Router, Schema
from ninja.errors import HttpError
from shipping.models import WalletNonce
from shipping.web3 import generate_siwe_nonce, parse_siwe_message, verify_siwe_signature
from web3 import Web3

auth_router = Router()


class RegisterIn(Schema):
    username: str
    email: str
    password: str


class LoginIn(Schema):
    username: str
    password: str


class AuthUserOut(Schema):
    id: Optional[int] = None
    username: str
    email: str
    is_authenticated: bool


class SiweNonceOut(Schema):
    address: str
    nonce: str


class SiweVerifyIn(Schema):
    message: str
    signature: str


class SiweVerifyOut(Schema):
    success: bool
    address: str
    username: str
    user_id: int


@auth_router.post("/register", response=AuthUserOut)
def register(request, payload: RegisterIn):
    """Registers a new standard user account."""
    if User.objects.filter(username=payload.username).exists():
        raise HttpError(400, "Username already taken")
    if payload.email and User.objects.filter(email=payload.email).exists():
        raise HttpError(400, "Email already registered")

    user = User.objects.create_user(
        username=payload.username,
        email=payload.email,
        password=payload.password,
    )
    login(request, user)
    return {
        "id": user.pk,
        "username": user.username,
        "email": user.email,
        "is_authenticated": True,
    }


@auth_router.post("/login", response=AuthUserOut)
def user_login(request, payload: LoginIn):
    """Authenticates and establishes a session for an existing user."""
    user = authenticate(request, username=payload.username, password=payload.password)
    if not user:
        raise HttpError(401, "Invalid username or password")

    login(request, user)
    return {
        "id": user.pk,
        "username": user.username,
        "email": user.email,
        "is_authenticated": True,
    }


@auth_router.post("/logout")
def user_logout(request):
    """Logs out the active session."""
    logout(request)
    return {"status": "logged_out"}


@auth_router.get("/me", response=AuthUserOut)
def get_current_user(request):
    """Returns profile information for the currently active user session."""
    if request.user.is_authenticated:
        return {
            "id": request.user.pk,
            "username": request.user.username,
            "email": request.user.email,
            "is_authenticated": True,
        }
    return {
        "id": None,
        "username": "AnonymousUser",
        "email": "",
        "is_authenticated": False,
    }


@auth_router.get("/siwe/nonce", response=SiweNonceOut)
def get_siwe_nonce(request, address: str):
    """
    Generates an EIP-4361 cryptographically secure SIWE nonce for an address.
    """
    try:
        checksum = Web3.to_checksum_address(address)
    except Exception:
        raise HttpError(400, "Invalid Ethereum address format")

    nonce_str = generate_siwe_nonce()
    WalletNonce.objects.update_or_create(
        address=checksum,
        defaults={"nonce": nonce_str},
    )
    return {"address": checksum, "nonce": nonce_str}


@auth_router.post("/siwe/verify", response=SiweVerifyOut)
def verify_siwe(request, payload: SiweVerifyIn):
    """
    Verifies a Sign-In with Ethereum (EIP-4361) signature and establishes a session.
    """
    parsed = parse_siwe_message(payload.message)

    address = parsed.get("address")
    if not address:
        raise HttpError(400, "Unable to extract address from SIWE message")

    try:
        checksum = Web3.to_checksum_address(address)
    except Exception:
        raise HttpError(400, "Invalid Ethereum address format in message")

    wallet_nonce = WalletNonce.objects.filter(address=checksum).first()
    expected_nonce = wallet_nonce.nonce if wallet_nonce else None

    is_valid, recovered_or_error, _ = verify_siwe_signature(
        payload.message,
        payload.signature,
        expected_nonce=expected_nonce,
    )
    if not is_valid:
        raise HttpError(400, f"SIWE verification failed: {recovered_or_error}")

    # Consume the nonce to avoid replay attacks
    if wallet_nonce:
        wallet_nonce.delete()

    # Get or create local Django User for this Ethereum address
    user, _ = User.objects.get_or_create(
        username=checksum.lower(),
        defaults={"email": f"{checksum.lower()}@ethereum.eth"},
    )
    login(request, user)

    return {
        "success": True,
        "address": checksum,
        "username": user.username,
        "user_id": user.pk,
    }
