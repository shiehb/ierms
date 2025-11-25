"""
URL configuration for help app.
"""
from django.urls import path
from . import views

urlpatterns = [
    path('topics/', views.get_topics, name='get-help-topics'),
    path('categories/', views.get_categories, name='get-help-categories'),
    path('topics/save/', views.save_topics, name='save-help-topics'),
    path('categories/save/', views.save_categories, name='save-help-categories'),
    path('backup/', views.export_backup, name='export-help-backup'),
    path('restore/', views.restore_backup, name='restore-help-backup'),
    path('upload-image/', views.upload_help_image, name='upload-help-image'),
]

