from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from establishments.views import EstablishmentViewSet
from audit.views import ActivityLogViewSet
from .views import GlobalSearchView, SearchFilterOptionsView, SearchSuggestionsView  

# DRF router for ViewSets
router = DefaultRouter()
router.register(r'establishments', EstablishmentViewSet, basename='establishment')
router.register(r'activity-logs', ActivityLogViewSet, basename='activitylog')
router.register(r'audit-logs', ActivityLogViewSet, basename='auditlog')
# Note: InspectionViewSet is registered in inspections/urls.py to allow custom endpoints

urlpatterns = [
    path('admin/', admin.site.urls),

    # Users / Notifications / System config
    path('api/auth/', include('users.urls')),
    path('api/notifications/', include('notifications.urls')),
    path('api/reports/', include('reports.urls')),
    path('api/help/', include('help.urls')),
    path('api/', include('laws.urls')),

    # 🔹 Backup & Restore endpoints
    path('api/db/', include('system.urls')),   # <---- add this line

    # Include inspections URLs (contains billing endpoints)
    path('api/', include('inspections.urls')),

    # Search
    path('api/search/', GlobalSearchView.as_view()),
    path('api/search/suggestions/', SearchSuggestionsView.as_view()),
    path('api/search/options/', SearchFilterOptionsView.as_view()),

    # DRF router
    path('api/', include(router.urls)),
]

# Serve static files during development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
