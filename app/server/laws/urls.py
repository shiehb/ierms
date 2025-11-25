from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import LawViewSet

# Create router and register viewsets
router = DefaultRouter()
router.register(r'laws', LawViewSet, basename='law')

urlpatterns = [
    path('', include(router.urls)),
]


