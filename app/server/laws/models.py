from django.db import models
from django.core.exceptions import ValidationError


class Law(models.Model):
    """
    Model for managing environmental laws and regulations.
    """
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
    ]
    
    law_title = models.CharField(
        max_length=255,
        help_text="Full title of the law or regulation"
    )
    reference_code = models.CharField(
        max_length=100,
        unique=True,
        blank=True,
        null=True,
        help_text="Reference code (e.g., RA 8749, PD-1586)"
    )
    description = models.TextField(
        help_text="Detailed description of the law's scope and intent"
    )
    category = models.CharField(
        max_length=100,
        help_text="Category of the law (e.g., Environmental Impact Assessment)"
    )
    effective_date = models.DateField(
        help_text="Date when the law became effective"
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='Active',
        help_text="Current status of the law"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Law'
        verbose_name_plural = 'Laws'
        indexes = [
            models.Index(fields=['law_title']),
            models.Index(fields=['reference_code']),
            models.Index(fields=['category']),
            models.Index(fields=['status']),
            models.Index(fields=['effective_date']),
        ]
    
    def __str__(self):
        if self.reference_code:
            return f"{self.reference_code} - {self.law_title}"
        return self.law_title
    
    def clean(self):
        """Validate model fields"""
        super().clean()
        
        # Validate reference_code uniqueness (case-insensitive)
        if self.reference_code:
            existing = Law.objects.filter(
                reference_code__iexact=self.reference_code
            ).exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError({
                    'reference_code': 'A law with this reference code already exists.'
                })
    
    def save(self, *args, **kwargs):
        """Override save to run validation"""
        self.full_clean()
        super().save(*args, **kwargs)


