from django.conf import settings
from ninja import NinjaAPI, Schema

from .qa.router import qa_router
from .routers.auth import auth_router
from .routers.feeds import feeds_router
from .routers.payments import payments_router
from .routers.shop import shop_router
from .routers.social import social_router

api = NinjaAPI(
    title="Atria API",
    version="1.0.0",
    description="Atria Decentralized Social Marketplace & Knowledge Economy API",
    urls_namespace="atria_api",
)


class HealthResponse(Schema):
    status: str
    platform: str
    debug: bool


class SystemInfoResponse(Schema):
    name: str
    version: str
    federation_protocol: str
    site_domain: str


@api.get("/health", response=HealthResponse, tags=["system"])
def health_check(request):
    """Health check endpoint for container and uptime monitoring."""
    return {
        "status": "ok",
        "platform": "atria",
        "debug": bool(settings.DEBUG),
    }


@api.get("/system/info", response=SystemInfoResponse, tags=["system"])
def system_info(request):
    """Basic platform metadata and configuration info."""
    return {
        "name": "Atria",
        "version": "1.0.0",
        "federation_protocol": "ActivityPub",
        "site_domain": getattr(settings, "SITE_DOMAIN", "localhost:8000"),
    }


# Register unified routers
api.add_router("/auth", auth_router, tags=["auth"])
api.add_router("/social", social_router, tags=["social"])
api.add_router("/shop", shop_router, tags=["shop"])
api.add_router("/payments", payments_router, tags=["payments"])
api.add_router("/feeds", feeds_router, tags=["feeds"])
api.add_router("/qa", qa_router, tags=["qa"])
