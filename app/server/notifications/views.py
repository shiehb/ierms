# notifications/views.py
from rest_framework import generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Notification
from .serializers import NotificationSerializer
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required

User = get_user_model()

class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).order_by('-created_at')

class MarkNotificationAsReadView(generics.UpdateAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Notification.objects.all()
    
    def post(self, request, *args, **kwargs):  # Add POST method
        return self.update(request, *args, **kwargs)
    
    def update(self, request, *args, **kwargs):
        notification = self.get_object()
        if notification.recipient != request.user:
            return Response({'detail': 'Not found.'}, status=404)
        
        notification.is_read = True
        notification.save()
        return Response({'status': 'marked as read'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_notifications_read(request):
    try:
        # Mark all unread notifications for the current user as read
        Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        return Response({'status': 'all notifications marked as read'})
    except Exception as e:
        return Response({'detail': str(e)}, status=400)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def unread_notifications_count(request):
    try:
        count = Notification.objects.filter(recipient=request.user, is_read=False).count()
        return Response({'count': count})
    except Exception as e:
        return Response({'detail': str(e)}, status=400)

# notifications/views.py - Add this function
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_notification(request, pk):
    try:
        notification = Notification.objects.get(pk=pk, recipient=request.user)
        notification.delete()
        return Response({'status': 'notification deleted'})
    except Notification.DoesNotExist:
        return Response({'detail': 'Notification not found.'}, status=status.HTTP_404_NOT_FOUND)
    
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_all_notifications(request):
    try:
        # Delete all notifications for the current user
        Notification.objects.filter(recipient=request.user).delete()
        return Response({'status': 'all notifications deleted'})
    except Exception as e:
        return Response({'detail': str(e)}, status=400)


@login_required
def unread_count(request):
    count = request.user.notification_set.filter(is_read=False).count()
    return JsonResponse({'unread_count': count})