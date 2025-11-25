from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils import timezone


class BusinessType(models.Model):
    """Normalized model for business types/nature of business"""
    code = models.CharField(max_length=50, unique=True, help_text="Business type code")
    name = models.CharField(max_length=255, help_text="Business type name")
    description = models.TextField(blank=True, null=True, help_text="Description of the business type")
    category = models.CharField(max_length=100, blank=True, null=True, help_text="Business category (e.g., Manufacturing, Service, Retail)")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['category', 'name']
        verbose_name = "Business Type"
        verbose_name_plural = "Business Types"
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class Province(models.Model):
    """Normalized model for provinces"""
    code = models.CharField(max_length=10, unique=True, help_text="Province code (e.g., LU, IN, IS, PAN)")
    name = models.CharField(max_length=100, help_text="Province name")
    region = models.CharField(max_length=100, blank=True, null=True, help_text="Region the province belongs to")
    description = models.TextField(blank=True, null=True, help_text="Description of the province")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['region', 'name']
        verbose_name = "Province"
        verbose_name_plural = "Provinces"
    
    def __str__(self):
        return f"{self.name} ({self.region})"


class City(models.Model):
    """Normalized model for cities/municipalities"""
    code = models.CharField(max_length=20, unique=True, help_text="City code")
    name = models.CharField(max_length=100, help_text="City name")
    province = models.ForeignKey(Province, on_delete=models.CASCADE, related_name="cities", help_text="Province the city belongs to")
    city_type = models.CharField(max_length=20, choices=[
        ('CITY', 'City'),
        ('MUNICIPALITY', 'Municipality'),
        ('COMPONENT_CITY', 'Component City'),
        ('HIGHLY_URBANIZED_CITY', 'Highly Urbanized City'),
        ('INDEPENDENT_COMPONENT_CITY', 'Independent Component City')
    ], default='MUNICIPALITY', help_text="Type of city/municipality")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['province', 'name']
        verbose_name = "City"
        verbose_name_plural = "Cities"
        unique_together = ['name', 'province']
    
    def __str__(self):
        return f"{self.name}, {self.province.name}"


class Barangay(models.Model):
    """Normalized model for barangays"""
    code = models.CharField(max_length=20, unique=True, help_text="Barangay code")
    name = models.CharField(max_length=100, help_text="Barangay name")
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name="barangays", help_text="City the barangay belongs to")
    barangay_type = models.CharField(max_length=20, choices=[
        ('URBAN', 'Urban'),
        ('RURAL', 'Rural')
    ], default='URBAN', help_text="Type of barangay")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['city', 'name']
        verbose_name = "Barangay"
        verbose_name_plural = "Barangays"
        unique_together = ['name', 'city']
    
    def __str__(self):
        return f"{self.name}, {self.city.name}"


class EstablishmentStatus(models.Model):
    """Normalized model for establishment status"""
    code = models.CharField(max_length=20, unique=True, help_text="Status code")
    name = models.CharField(max_length=100, help_text="Status name")
    description = models.TextField(blank=True, null=True, help_text="Description of the status")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = "Establishment Status"
        verbose_name_plural = "Establishment Statuses"
    
    def __str__(self):
        return self.name


class EstablishmentType(models.Model):
    """Normalized model for establishment types"""
    code = models.CharField(max_length=20, unique=True, help_text="Establishment type code")
    name = models.CharField(max_length=100, help_text="Establishment type name")
    description = models.TextField(blank=True, null=True, help_text="Description of the establishment type")
    requires_license = models.BooleanField(default=True, help_text="Whether this type requires a license")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = "Establishment Type"
        verbose_name_plural = "Establishment Types"
    
    def __str__(self):
        return self.name


class Establishment(models.Model):
    """Normalized Establishment model with foreign key relationships"""
    # Basic Information
    name = models.CharField(max_length=255, help_text="Establishment name")
    registration_number = models.CharField(max_length=50, unique=True, blank=True, null=True, help_text="Business registration number")
    tin_number = models.CharField(max_length=20, blank=True, null=True, help_text="Tax Identification Number")
    
    # Normalized relationships
    business_type = models.ForeignKey(BusinessType, on_delete=models.PROTECT, related_name="establishments", help_text="Type of business")
    establishment_type = models.ForeignKey(EstablishmentType, on_delete=models.PROTECT, related_name="establishments", help_text="Type of establishment")
    status = models.ForeignKey(EstablishmentStatus, on_delete=models.PROTECT, related_name="establishments", default=1, help_text="Current status")
    
    # Location Information (normalized)
    province = models.ForeignKey(Province, on_delete=models.PROTECT, related_name="establishments", help_text="Province")
    city = models.ForeignKey(City, on_delete=models.PROTECT, related_name="establishments", help_text="City/Municipality")
    barangay = models.ForeignKey(Barangay, on_delete=models.PROTECT, related_name="establishments", help_text="Barangay")
    street_building = models.CharField(max_length=255, help_text="Street address and building details")
    postal_code = models.CharField(max_length=10, blank=True, null=True, help_text="Postal code")
    
    # Coordinates and Geometry
    latitude = models.DecimalField(max_digits=9, decimal_places=6, help_text="Latitude coordinate")
    longitude = models.DecimalField(max_digits=9, decimal_places=6, help_text="Longitude coordinate")
    polygon = models.JSONField(blank=True, null=True, help_text="Establishment boundary polygon as JSON")
    
    # Business Information
    year_established = models.PositiveIntegerField(help_text="Year the establishment was established")
    employee_count = models.PositiveIntegerField(blank=True, null=True, help_text="Number of employees")
    capital_investment = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True, help_text="Capital investment amount")
    
    # Contact Information
    contact_person = models.CharField(max_length=255, blank=True, null=True, help_text="Primary contact person")
    contact_phone = models.CharField(max_length=20, blank=True, null=True, help_text="Contact phone number")
    contact_email = models.EmailField(blank=True, null=True, help_text="Contact email address")
    website = models.URLField(blank=True, null=True, help_text="Establishment website")
    
    # Compliance Information
    license_number = models.CharField(max_length=100, blank=True, null=True, help_text="Business license number")
    license_expiry = models.DateField(blank=True, null=True, help_text="License expiry date")
    permit_number = models.CharField(max_length=100, blank=True, null=True, help_text="Environmental permit number")
    permit_expiry = models.DateField(blank=True, null=True, help_text="Environmental permit expiry date")
    
    # Audit and Tracking
    is_active = models.BooleanField(default=True, help_text="Whether the establishment is active")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_establishments", help_text="User who created this establishment")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="updated_establishments", help_text="User who last updated this establishment")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['business_type']),
            models.Index(fields=['establishment_type']),
            models.Index(fields=['status']),
            models.Index(fields=['province', 'city', 'barangay']),
            models.Index(fields=['is_active']),
            models.Index(fields=['created_at']),
            models.Index(fields=['business_type', 'province']),
            models.Index(fields=['status', 'is_active']),
        ]
        verbose_name = "Establishment"
        verbose_name_plural = "Establishments"
    
    def __str__(self):
        return f"{self.name} ({self.business_type.name})"
    
    def clean(self):
        """Validate establishment data"""
        # Check for case-insensitive name duplicates
        if Establishment.objects.filter(
            name__iexact=self.name
        ).exclude(pk=self.pk).exists():
            raise ValidationError({'name': 'An establishment with this name already exists.'})
        
        # Validate year_established
        current_year = timezone.now().year
        if self.year_established and (self.year_established < 1800 or self.year_established > current_year):
            raise ValidationError({
                'year_established': f'Year established must be between 1800 and {current_year}'
            })
        
        # Validate coordinates
        if self.latitude and (self.latitude < -90 or self.latitude > 90):
            raise ValidationError({'latitude': 'Latitude must be between -90 and 90'})
        
        if self.longitude and (self.longitude < -180 or self.longitude > 180):
            raise ValidationError({'longitude': 'Longitude must be between -180 and 180'})
        
        # Validate location hierarchy
        if self.barangay and self.barangay.city != self.city:
            raise ValidationError({
                'barangay': 'Barangay must belong to the selected city'
            })
        
        if self.city and self.city.province != self.province:
            raise ValidationError({
                'city': 'City must belong to the selected province'
            })
    
    def save(self, *args, **kwargs):
        """Override save to run validation"""
        self.full_clean()
        super().save(*args, **kwargs)
    
    def get_full_address(self):
        """Get the complete address as a string"""
        address_parts = [
            self.street_building,
            self.barangay.name if self.barangay else '',
            self.city.name if self.city else '',
            self.province.name if self.province else ''
        ]
        return ', '.join(filter(None, address_parts))
    
    def get_location_hierarchy(self):
        """Get the complete location hierarchy"""
        return {
            'province': self.province.name if self.province else None,
            'city': self.city.name if self.city else None,
            'barangay': self.barangay.name if self.barangay else None,
            'street': self.street_building,
            'postal_code': self.postal_code
        }
    
    def is_license_expired(self):
        """Check if the establishment's license is expired"""
        if not self.license_expiry:
            return False
        return self.license_expiry < timezone.now().date()
    
    def is_permit_expired(self):
        """Check if the establishment's permit is expired"""
        if not self.permit_expiry:
            return False
        return self.permit_expiry < timezone.now().date()
    
    def get_compliance_status(self):
        """Get the overall compliance status"""
        if self.is_license_expired() or self.is_permit_expired():
            return 'NON_COMPLIANT'
        elif self.license_expiry and (self.license_expiry - timezone.now().date()).days <= 30:
            return 'EXPIRING_SOON'
        else:
            return 'COMPLIANT'


class EstablishmentHistory(models.Model):
    """Track changes to establishment records"""
    establishment = models.ForeignKey(Establishment, on_delete=models.CASCADE, related_name="history")
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    change_type = models.CharField(max_length=20, choices=[
        ('CREATE', 'Created'),
        ('UPDATE', 'Updated'),
        ('STATUS_CHANGE', 'Status Changed'),
        ('LOCATION_CHANGE', 'Location Changed'),
        ('BUSINESS_CHANGE', 'Business Type Changed'),
        ('CONTACT_CHANGE', 'Contact Information Changed'),
        ('COMPLIANCE_CHANGE', 'Compliance Information Changed')
    ])
    old_values = models.JSONField(blank=True, null=True, help_text="Previous values")
    new_values = models.JSONField(blank=True, null=True, help_text="New values")
    reason = models.TextField(blank=True, null=True, help_text="Reason for the change")
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Establishment History"
        verbose_name_plural = "Establishment Histories"
    
    def __str__(self):
        return f"{self.establishment.name} - {self.change_type} at {self.timestamp}"


class EstablishmentDocument(models.Model):
    """Model for storing establishment-related documents"""
    establishment = models.ForeignKey(Establishment, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=50, choices=[
        ('LICENSE', 'Business License'),
        ('PERMIT', 'Environmental Permit'),
        ('REGISTRATION', 'Business Registration'),
        ('CERTIFICATE', 'Certificate'),
        ('OTHER', 'Other')
    ])
    title = models.CharField(max_length=255, help_text="Document title")
    description = models.TextField(blank=True, null=True, help_text="Document description")
    file_path = models.CharField(max_length=500, help_text="Path to the document file")
    file_size = models.PositiveIntegerField(blank=True, null=True, help_text="File size in bytes")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = "Establishment Document"
        verbose_name_plural = "Establishment Documents"
    
    def __str__(self):
        return f"{self.establishment.name} - {self.title}"


# Manager classes for better querying
class EstablishmentManager(models.Manager):
    """Manager for Establishment with enhanced querying"""
    
    def with_location_info(self):
        """Get establishments with location information"""
        return self.select_related(
            'business_type', 'establishment_type', 'status',
            'province', 'city', 'barangay'
        )
    
    def by_province(self, province_code):
        """Get establishments by province"""
        return self.filter(province__code=province_code)
    
    def by_city(self, city_code):
        """Get establishments by city"""
        return self.filter(city__code=city_code)
    
    def by_business_type(self, business_type_code):
        """Get establishments by business type"""
        return self.filter(business_type__code=business_type_code)
    
    def by_status(self, status_code):
        """Get establishments by status"""
        return self.filter(status__code=status_code)
    
    def active(self):
        """Get active establishments"""
        return self.filter(is_active=True)
    
    def with_expired_licenses(self):
        """Get establishments with expired licenses"""
        from django.utils import timezone
        return self.filter(license_expiry__lt=timezone.now().date())
    
    def with_expiring_licenses(self, days=30):
        """Get establishments with licenses expiring soon"""
        from django.utils import timezone
        from datetime import timedelta
        expiry_date = timezone.now().date() + timedelta(days=days)
        return self.filter(
            license_expiry__lte=expiry_date,
            license_expiry__gte=timezone.now().date()
        )


# Add manager to Establishment model
Establishment.objects = EstablishmentManager()
