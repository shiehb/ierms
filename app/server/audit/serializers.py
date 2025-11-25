from rest_framework import serializers
from .models import ActivityLog


class ActivityLogSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    user_email = serializers.SerializerMethodField()
    action_type = serializers.CharField(source="action", read_only=True)
    metadata_status = serializers.SerializerMethodField()

    class Meta:
        model = ActivityLog
        fields = [
            "id",
            "user",
            "user_name",
            "user_email",
            "role",
            "action",
            "action_type",
            "module",
            "description",
            "message",
            "metadata",
            "metadata_status",
            "ip_address",
            "user_agent",
            "created_at",
        ]
        read_only_fields = fields

    def get_user_name(self, obj):
        if obj.user and hasattr(obj.user, "get_full_name"):
            full_name = obj.user.get_full_name()
            if full_name:
                return full_name
        if obj.user and getattr(obj.user, "email", None):
            return obj.user.email
        return "System"

    def get_user_email(self, obj):
        if obj.user and getattr(obj.user, "email", None):
            return obj.user.email
        return ""

    @staticmethod
    def get_metadata_status(obj):
        status = (obj.metadata or {}).get("status")
        return status or "success"