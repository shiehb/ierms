# notifications/urls.py
from django.urls import path
from . import views
from .views import unread_count

urlpatterns = [
    path('', views.NotificationListView.as_view(), name='notification-list'),
    path('<int:pk>/read/', views.MarkNotificationAsReadView.as_view(), name='mark-notification-read'),
    path('mark-all-read/', views.mark_all_notifications_read, name='mark-all-notifications-read'),
    path('unread-count/', views.unread_notifications_count, name='unread-notifications-count'),
    path('<int:pk>/delete/', views.delete_notification, name='delete-notification'),
    path('delete-all/', views.delete_all_notifications, name='delete-all-notifications'),
    path('notifications/unread-count/', unread_count, name='notifications-unread-count'),
]