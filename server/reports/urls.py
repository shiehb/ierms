from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    # Centralized Report Dashboard endpoints
    path('access/', views.get_report_access, name='report-access'),
    path('generate/', views.generate_report, name='generate-report'),
    path('filter-options/', views.get_filter_options, name='filter-options'),
]
