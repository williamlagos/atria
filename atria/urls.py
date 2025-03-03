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
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path

# from socialize.socialize.urls import urlpatterns as socialize_patterns
# from shipping.shipping.urls import urlpatterns as shipping_patterns
# from plethora.plethora.urls import urlpatterns as plethora_patterns
# from emporio.emporio.urls import urlpatterns as emporio_patterns
# from feedly.feedly.urls import urlpatterns as feedly_patterns

from .apis import *
from .admin import dashboard


class HealthCheckView(View):
    def get(self, request):
        return JsonResponse({'health': 'success'})


urlpatterns = [
    path('', HealthCheckView.as_view()),
    path('dashboard/', dashboard.urls),
    path('v1/', include([
        path('accounts/', include(AccountResource.urls())),
        path('deliveries/', include(DeliveryResource.urls())),
        path('products/', include(ProductResource.urls())),
        path('contents/', include(ContentResource.urls())),
        path('blocks/', include(BlockResource.urls())),
        path('baskets/', include(BasketResource.urls())),
        path('orders/', include(OrderResource.urls())),
        path('rates/', include(RateResource.urls())),
    ]))
    # path('socialize/', include(socialize_patterns)),
    # path('shipping/', include(shipping_patterns)),
    # path('plethora/', include(plethora_patterns)),
    # path('emporio/', include(emporio_patterns)),
    # path('feedly/', include(feedly_patterns)),
]
