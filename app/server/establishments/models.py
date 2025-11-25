# establishments/models.py
from django.db import models
from django.core.exceptions import ValidationError

class Establishment(models.Model):
    name = models.CharField(max_length=255, unique=True)
    nature_of_business = models.CharField(max_length=255)
    year_established = models.CharField(max_length=4)
    
    # Address fields
    province = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    barangay = models.CharField(max_length=100)
    street_building = models.CharField(max_length=255)
    postal_code = models.CharField(max_length=4)
    
    # Coordinates
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    
    # Store polygon as JSON in database
    polygon = models.JSONField(blank=True, null=True)
    
    # Marker icon type (stores the key from ESTABLISHMENT_ICON_MAP)
    marker_icon = models.CharField(max_length=100, blank=True, null=True)
    
    # Status and timestamps
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name

    def clean(self):
        # Check for case-insensitive duplicates
        if Establishment.objects.filter(
            name__iexact=self.name
        ).exclude(pk=self.pk).exists():
            raise ValidationError({'name': 'An establishment with this name already exists.'})
    
    def save(self, *args, **kwargs):
        self.full_clean()  # Run validation before saving
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['nature_of_business']),
            models.Index(fields=['city']),
            models.Index(fields=['barangay']),
        ]