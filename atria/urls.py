"""contents URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.views import View
from django.http import JsonResponse
from django.urls import include, path

from .apis import *


class HealthCheckView(View):
    def get(self, request):
        return JsonResponse({'health': 'success'})


urlpatterns = [
    path('', HealthCheckView.as_view()),
    path('v1/', include([
        path('accounts/', include(AccountResource.urls())),
        path('deliveries/', include(DeliveryResource.urls())),
        path('rates/', include(RateResource.urls())),
    ]))
]
