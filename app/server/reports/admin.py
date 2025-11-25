from django.contrib import admin
from django.utils.html import format_html
from .models import AccomplishmentReport, ReportMetric


@admin.register(AccomplishmentReport)
class AccomplishmentReportAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'report_type', 'quarter', 'year', 'period_start', 'period_end',
        'created_by', 'created_at', 'completed_inspections_count'
    ]
    list_filter = ['report_type', 'quarter', 'year', 'created_at', 'period_start', 'period_end']
    search_fields = ['title', 'summary', 'key_achievements', 'created_by__username', 'created_by__email']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'report_type', 'quarter', 'year', 'period_start', 'period_end')
        }),
        ('Content', {
            'fields': ('summary', 'key_achievements', 'completed_inspections')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def completed_inspections_count(self, obj):
        return obj.completed_inspections.count()
    completed_inspections_count.short_description = 'Inspections Count'
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if not request.user.is_superuser:
            # Non-superusers can only see their own reports
            queryset = queryset.filter(created_by=request.user)
        return queryset
    
    def save_model(self, request, obj, form, change):
        if not change:  # Creating new object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ReportMetric)
class ReportMetricAdmin(admin.ModelAdmin):
    list_display = [
        'report', 'total_inspections', 'compliant_inspections', 'non_compliant_inspections', 
        'compliance_rate', 'created_at'
    ]
    list_filter = ['report__report_type', 'report__quarter', 'report__year', 'created_at']
    search_fields = ['report__title']
    raw_id_fields = ['report']
    readonly_fields = ['created_at']
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if not request.user.is_superuser:
            # Non-superusers can only see metrics for their own reports
            queryset = queryset.filter(report__created_by=request.user)
        return queryset
