"""Atria URL Configuration

The `urlpatterns` list routes URLs to views.
"""
from django.http import JsonResponse
from django.urls import include, path
from django.views import View

from .api import api


class HealthCheckView(View):
    def get(self, request):
        return JsonResponse({'health': 'success', 'status': 'ok'})


urlpatterns = [
    # System health check at root
    path('', HealthCheckView.as_view(), name='health-check'),

    # Modern REST API (Django Ninja with OpenAPI docs at /api/v1/docs)
    path('api/v1/', api.urls),

    # Federated social network (ActivityPub, WebFinger, Actors, Inboxes)
    path('', include('socialize.socialize.urls')),

    # E-commerce marketplace (Products, Cart, Orders, Deliveries)
    path('shop/', include('shipping.shipping.urls')),
]
