# establishments/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EstablishmentViewSet

router = DefaultRouter()
router.register(r'establishments', EstablishmentViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('search/', EstablishmentViewSet.as_view({'get': 'search'}), name='establishment-search'),
]