from django.urls import path
from . import views

urlpatterns = [
    path("backup/", views.backup_database, name="backup"),
    path("restore/", views.restore_database, name="restore"),
    path("backups/", views.list_backups, name="list_backups"),
    path("delete/<str:file_name>/", views.delete_backup, name="delete_backup"),
    path("download/<str:file_name>/", views.download_backup, name="download_backup"),
]