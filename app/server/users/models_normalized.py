from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone
from django.core.exceptions import ValidationError
from core.settings import generate_secure_password


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, password_provided=False, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        if not password:
            # Use auto-generated password
            password = generate_secure_password()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        
        # Send signal for welcome email if password was auto-generated
        if not password_provided:
            from .signals import user_created_with_password
            user_created_with_password.send(
                sender=self.__class__,
                user=user,
                password=password
            )
        
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        return self.create_user(email, password, **extra_fields)


class UserLevel(models.Model):
    """Normalized model for user levels/roles"""
    code = models.CharField(max_length=50, unique=True, help_text="User level code (e.g., 'Admin', 'Section Chief')")
    name = models.CharField(max_length=100, help_text="Display name for the user level")
    description = models.TextField(blank=True, null=True, help_text="Description of the user level")
    requires_section = models.BooleanField(default=False, help_text="Whether this user level requires a section assignment")
    requires_district = models.BooleanField(default=False, help_text="Whether this user level requires a district assignment")
    max_active_users = models.PositiveIntegerField(null=True, blank=True, help_text="Maximum number of active users for this level (null = unlimited)")
    max_active_per_section = models.PositiveIntegerField(null=True, blank=True, help_text="Maximum active users per section (null = unlimited)")
    max_active_per_district = models.PositiveIntegerField(null=True, blank=True, help_text="Maximum active users per district (null = unlimited)")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['code']
        verbose_name = "User Level"
        verbose_name_plural = "User Levels"
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    def clean(self):
        """Validate user level constraints"""
        if self.max_active_users is not None and self.max_active_users < 1:
            raise ValidationError({'max_active_users': 'Maximum active users must be at least 1'})
        if self.max_active_per_section is not None and self.max_active_per_section < 1:
            raise ValidationError({'max_active_per_section': 'Maximum active per section must be at least 1'})
        if self.max_active_per_district is not None and self.max_active_per_district < 1:
            raise ValidationError({'max_active_per_district': 'Maximum active per district must be at least 1'})


class Section(models.Model):
    """Normalized model for sections/laws"""
    code = models.CharField(max_length=50, unique=True, help_text="Section code (e.g., 'PD-1586', 'RA-8749')")
    name = models.CharField(max_length=200, help_text="Full name of the section/law")
    description = models.TextField(blank=True, null=True, help_text="Description of the section/law")
    is_combined = models.BooleanField(default=False, help_text="Whether this is a combined section")
    combined_sections = models.ManyToManyField('self', blank=True, symmetrical=False, help_text="Sections that are combined in this section")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['code']
        verbose_name = "Section"
        verbose_name_plural = "Sections"
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    def clean(self):
        """Validate section constraints"""
        if self.is_combined and not self.combined_sections.exists():
            raise ValidationError({'combined_sections': 'Combined sections must have at least one section assigned'})
        if not self.is_combined and self.combined_sections.exists():
            raise ValidationError({'combined_sections': 'Non-combined sections cannot have combined sections assigned'})


class District(models.Model):
    """Normalized model for districts"""
    code = models.CharField(max_length=50, unique=True, help_text="District code")
    name = models.CharField(max_length=100, help_text="Full name of the district")
    province = models.CharField(max_length=100, help_text="Province the district belongs to")
    description = models.TextField(blank=True, null=True, help_text="Description of the district")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['province', 'name']
        verbose_name = "District"
        verbose_name_plural = "Districts"
    
    def __str__(self):
        return f"{self.name} ({self.province})"


class UserProfile(models.Model):
    """Extended user profile information"""
    user = models.OneToOneField('User', on_delete=models.CASCADE, related_name='profile')
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    emergency_contact = models.CharField(max_length=255, blank=True, null=True)
    emergency_phone = models.CharField(max_length=20, blank=True, null=True)
    notes = models.TextField(blank=True, null=True, help_text="Additional notes about the user")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"
    
    def __str__(self):
        return f"Profile for {self.user.email}"


class User(AbstractBaseUser, PermissionsMixin):
    """Normalized User model with foreign key relationships"""
    email = models.EmailField(unique=True, max_length=255)
    first_name = models.CharField(max_length=150, blank=True)
    middle_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    
    # Normalized relationships
    userlevel = models.ForeignKey(UserLevel, on_delete=models.PROTECT, related_name="users", help_text="User level/role")
    section = models.ForeignKey(Section, on_delete=models.PROTECT, null=True, blank=True, related_name="users", help_text="Section/law assignment")
    district = models.ForeignKey(District, on_delete=models.PROTECT, null=True, blank=True, related_name="users", help_text="District assignment")
    
    # Django auth fields
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Password management
    is_first_login = models.BooleanField(default=True)
    must_change_password = models.BooleanField(default=False)
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
    class Meta:
        ordering = ['-date_joined']
        indexes = [
            models.Index(fields=['userlevel']),
            models.Index(fields=['section']),
            models.Index(fields=['district']),
            models.Index(fields=['is_active']),
            models.Index(fields=['userlevel', 'section', 'district']),
        ]
    
    def __str__(self):
        return f"{self.email} ({self.userlevel.code})"
    
    def clean(self):
        """Validate user constraints based on user level requirements"""
        if not self.userlevel:
            return
        
        # Check if section is required
        if self.userlevel.requires_section and not self.section:
            raise ValidationError({
                'section': f'Section is required for {self.userlevel.code} users'
            })
        
        # Check if district is required
        if self.userlevel.requires_district and not self.district:
            raise ValidationError({
                'district': f'District is required for {self.userlevel.code} users'
            })
        
        # Check maximum active users constraints
        if self.is_active:
            self._validate_user_level_constraints()
    
    def _validate_user_level_constraints(self):
        """Validate user level constraints"""
        # Check maximum active users for this level
        if self.userlevel.max_active_users is not None:
            active_count = User.objects.filter(
                userlevel=self.userlevel,
                is_active=True
            ).exclude(pk=self.pk).count()
            
            if active_count >= self.userlevel.max_active_users:
                raise ValidationError({
                    'userlevel': f'Maximum {self.userlevel.max_active_users} active {self.userlevel.code} users allowed'
                })
        
        # Check maximum active users per section
        if self.section and self.userlevel.max_active_per_section is not None:
            active_count = User.objects.filter(
                userlevel=self.userlevel,
                section=self.section,
                is_active=True
            ).exclude(pk=self.pk).count()
            
            if active_count >= self.userlevel.max_active_per_section:
                raise ValidationError({
                    'section': f'Maximum {self.userlevel.max_active_per_section} active {self.userlevel.code} users allowed per section'
                })
        
        # Check maximum active users per district
        if self.district and self.userlevel.max_active_per_district is not None:
            active_count = User.objects.filter(
                userlevel=self.userlevel,
                district=self.district,
                is_active=True
            ).exclude(pk=self.pk).count()
            
            if active_count >= self.userlevel.max_active_per_district:
                raise ValidationError({
                    'district': f'Maximum {self.userlevel.max_active_per_district} active {self.userlevel.code} users allowed per district'
                })
    
    def save(self, *args, **kwargs):
        """Override save to run validation"""
        self.full_clean()
        super().save(*args, **kwargs)
    
    def get_full_name(self):
        """Get user's full name"""
        return f"{self.first_name} {self.middle_name} {self.last_name}".strip()
    
    def get_short_name(self):
        """Get user's short name"""
        return self.first_name or self.email.split('@')[0]
    
    def can_manage_users(self):
        """Check if user can manage other users"""
        return self.userlevel.code in ['Admin', 'Division Chief']
    
    def can_assign_districts(self):
        """Check if user can assign districts"""
        return self.userlevel.code in ['Admin', 'Section Chief', 'Unit Head']
    
    def get_available_sections(self):
        """Get sections available for this user level"""
        if self.userlevel.requires_section:
            return Section.objects.filter(is_active=True)
        return Section.objects.none()
    
    def get_available_districts(self):
        """Get districts available for this user level"""
        if self.userlevel.requires_district:
            return District.objects.filter(is_active=True)
        return District.objects.none()


class UserAssignmentHistory(models.Model):
    """Track user assignment changes"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="assignment_history")
    old_userlevel = models.ForeignKey(UserLevel, on_delete=models.SET_NULL, null=True, blank=True, related_name="old_assignments")
    new_userlevel = models.ForeignKey(UserLevel, on_delete=models.SET_NULL, null=True, blank=True, related_name="new_assignments")
    old_section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True, related_name="old_assignments")
    new_section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True, related_name="new_assignments")
    old_district = models.ForeignKey(District, on_delete=models.SET_NULL, null=True, blank=True, related_name="old_assignments")
    new_district = models.ForeignKey(District, on_delete=models.SET_NULL, null=True, blank=True, related_name="new_assignments")
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="assignment_changes")
    reason = models.TextField(blank=True, null=True, help_text="Reason for the assignment change")
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = "User Assignment History"
        verbose_name_plural = "User Assignment Histories"
    
    def __str__(self):
        return f"Assignment change for {self.user.email} at {self.timestamp}"


class UserPermission(models.Model):
    """Model for granular user permissions"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="permissions")
    permission_code = models.CharField(max_length=100, help_text="Permission code")
    permission_name = models.CharField(max_length=200, help_text="Human-readable permission name")
    description = models.TextField(blank=True, null=True, help_text="Description of the permission")
    is_granted = models.BooleanField(default=True, help_text="Whether the permission is granted or denied")
    granted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="granted_permissions")
    granted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True, help_text="When the permission expires (null = never)")
    
    class Meta:
        unique_together = ['user', 'permission_code']
        ordering = ['permission_code']
        verbose_name = "User Permission"
        verbose_name_plural = "User Permissions"
    
    def __str__(self):
        return f"{self.user.email} - {self.permission_code}"
    
    def is_active(self):
        """Check if permission is currently active"""
        if not self.is_granted:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True
