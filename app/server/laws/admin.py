from django.contrib import admin
from .models import Law


@admin.register(Law)
class LawAdmin(admin.ModelAdmin):
    list_display = ['reference_code', 'law_title', 'category', 'effective_date', 'status', 'created_at']
    list_filter = ['status', 'category', 'effective_date']
    search_fields = ['law_title', 'reference_code', 'description']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('law_title', 'reference_code', 'category', 'status')
        }),
        ('Details', {
            'fields': ('description', 'effective_date')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


