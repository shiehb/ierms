from datetime import datetime, timedelta

from django.db.models import Q
from rest_framework import permissions, viewsets

from .models import ActivityLog
from .serializers import ActivityLogSerializer


class ActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ActivityLog.objects.select_related("user").all()
    serializer_class = ActivityLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params

        parsed_date_from = None
        parsed_date_to = None

        raw_date_from = params.get("date_from")
        if raw_date_from:
            try:
                parsed_date_from = datetime.fromisoformat(raw_date_from)
            except ValueError:
                parsed_date_from = None

        raw_date_to = params.get("date_to")
        if raw_date_to:
            try:
                parsed_date_to = datetime.fromisoformat(raw_date_to)
            except ValueError:
                parsed_date_to = None

        today = datetime.utcnow().date()

        if parsed_date_from and parsed_date_from.date() > today:
            parsed_date_from = datetime.combine(today, datetime.min.time())

        if parsed_date_to and parsed_date_to.date() > today:
            parsed_date_to = datetime.combine(today, datetime.min.time())

        if parsed_date_from and parsed_date_to and parsed_date_to < parsed_date_from:
            parsed_date_from, parsed_date_to = parsed_date_to, parsed_date_from

        if parsed_date_from:
            start_dt = parsed_date_from.replace(hour=0, minute=0, second=0, microsecond=0)
            queryset = queryset.filter(created_at__gte=start_dt)

        if parsed_date_to:
            end_dt = parsed_date_to.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            queryset = queryset.filter(created_at__lt=end_dt)

        user_query = params.get("user")
        if user_query:
            queryset = queryset.filter(
                Q(user__email__icontains=user_query)
                | Q(user__first_name__icontains=user_query)
                | Q(user__last_name__icontains=user_query)
                | Q(metadata__entity_name__icontains=user_query)
                | Q(metadata__email__icontains=user_query)
            )

        role = params.get("role")
        if role:
            queryset = queryset.filter(role__icontains=role)

        action_type = params.get("action_type")
        if action_type:
            queryset = queryset.filter(action__iexact=action_type.lower())

        keyword = params.get("keyword") or params.get("search")
        if keyword:
            queryset = queryset.filter(
                Q(description__icontains=keyword)
                | Q(module__icontains=keyword)
                | Q(message__icontains=keyword)
            )

        ordering = params.get("ordering", "-created_at")
        allowed_fields = {"created_at", "action", "role", "module"}
        order_field = ordering.lstrip("-")
        if order_field not in allowed_fields:
            ordering = "-created_at"

        return queryset.order_by(ordering, "-created_at")
