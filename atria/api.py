from django.conf import settings
from ninja import NinjaAPI, Schema

api = NinjaAPI(
    title="Atria API",
    version="1.0.0",
    description="Atria Decentralized Social Marketplace API",
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
        "version": "0.1.0",
        "federation_protocol": "ActivityPub",
        "site_domain": getattr(settings, "SITE_DOMAIN", "localhost:8000"),
    }
