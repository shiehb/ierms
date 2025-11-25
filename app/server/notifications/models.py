# notifications/models.py
from django.db import models
from django.conf import settings

class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('new_user', 'New User Registration'),
        ('new_establishment', 'New Establishment Created'),
        ('password_reset', 'Password Reset Request'),
        ('new_inspection', 'New Inspection Assignment'),
        ('COMPLIANCE_EXPIRED', 'Compliance Deadline Expired'),
        ('COMPLIANCE_REMINDER', 'Compliance Deadline Reminder'),
        ('NOV_SENT', 'Notice of Violation Sent'),
        ('NOO_SENT', 'Notice of Order Sent'),
        ('INSPECTION_COMPLETED', 'Inspection Completed'),
        ('inspection_completed', 'Inspection Completed'),
        ('inspection_review', 'Inspection Review Required'),
        ('inspection_forward', 'Inspection Forwarded'),
        ('reinspection_reminder', 'Reinspection Reminder'),
        # Add other types as needed
    ]
    
    # Legacy field name for backward compatibility
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    # New field name (maps to same field)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, 
        related_name='user_notifications', null=True, blank=True)
    
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, 
        null=True, blank=True, related_name='sent_notifications')
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    
    # Related object tracking (for linking to inspections, establishments, etc.)
    related_object_type = models.CharField(max_length=50, blank=True, 
        help_text='Type of related object (e.g., inspection, establishment)')
    related_object_id = models.IntegerField(null=True, blank=True,
        help_text='ID of related object')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', '-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['related_object_type', 'related_object_id']),
        ]
    
    def save(self, *args, **kwargs):
        # Sync user and recipient fields for backward compatibility
        if self.user and not self.recipient_id:
            self.recipient = self.user
        elif self.recipient and not self.user_id:
            self.user = self.recipient
        super().save(*args, **kwargs)
    
    def __str__(self):
        recipient_email = self.recipient.email if self.recipient else (self.user.email if self.user else 'N/A')
        return f"{self.notification_type} - {recipient_email}"