# establishments/admin.py
from django.contrib import admin
from .models import Establishment

@admin.register(Establishment)
class EstablishmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'nature_of_business', 'city', 'is_active')
    list_filter = ('is_active', 'province', 'city')
    search_fields = ('name', 'nature_of_business', 'city')