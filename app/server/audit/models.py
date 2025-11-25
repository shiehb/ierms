from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class ActivityLog(models.Model):
    ACTION_CHOICES = [
        ("login", "Login"),
        ("logout", "Logout"),
        ("create", "Create"),
        ("update", "Update"),
        ("delete", "Delete"),
        ("backup", "Backup"),
        ("restore", "Restore"),
        ("system", "System"),
        ("view", "View"),
        ("other", "Other"),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    role = models.CharField(max_length=50, blank=True, null=True)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, default="other")
    module = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        user_display = getattr(self.user, "email", None) or str(self.user) if self.user else "System"
        return f"{user_display} - {self.action} at {self.created_at:%Y-%m-%d %H:%M:%S}"
