from django.contrib import admin
from .models import ActivityLog

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "role", "action", "module")
    list_filter = ("action", "role", "module", "created_at")
    search_fields = ("user__email", "description", "message", "module", "ip_address")
