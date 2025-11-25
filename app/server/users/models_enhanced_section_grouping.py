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
            password = generate_secure_password()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        
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


class SectionGroup(models.Model):
    """Model for grouping sections together"""
    code = models.CharField(max_length=50, unique=True, help_text="Section group code")
    name = models.CharField(max_length=200, help_text="Name of the section group")
    description = models.TextField(blank=True, null=True, help_text="Description of the section group")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = "Section Group"
        verbose_name_plural = "Section Groups"
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    def get_all_sections(self):
        """Get all sections in this group"""
        return self.sections.filter(is_active=True)
    
    def get_all_users(self):
        """Get all users assigned to any section in this group"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return User.objects.filter(section__in=self.get_all_sections(), is_active=True)


class Section(models.Model):
    """Enhanced model for sections/laws with better grouping support"""
    code = models.CharField(max_length=50, unique=True, help_text="Section code (e.g., 'PD-1586', 'RA-8749')")
    name = models.CharField(max_length=200, help_text="Full name of the section/law")
    description = models.TextField(blank=True, null=True, help_text="Description of the section/law")
    
    # Section grouping
    section_group = models.ForeignKey(
        SectionGroup, 
        on_delete=models.SET_NULL, 
        null=True, blank=True, 
        related_name="sections",
        help_text="Section group this section belongs to"
    )
    
    # For combined sections (legacy support)
    is_combined = models.BooleanField(default=False, help_text="Whether this is a combined section")
    combined_sections = models.ManyToManyField(
        'self', 
        blank=True, 
        symmetrical=False, 
        related_name="parent_sections",
        help_text="Sections that are combined in this section"
    )
    
    # Section hierarchy
    parent_section = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, blank=True, 
        related_name="subsections",
        help_text="Parent section if this is a subsection"
    )
    
    # Section properties
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['section_group', 'code']
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
    
    def get_all_subsections(self):
        """Get all subsections recursively"""
        subsections = list(self.subsections.filter(is_active=True))
        for subsection in subsections:
            subsections.extend(subsection.get_all_subsections())
        return subsections
    
    def get_all_users_in_group(self):
        """Get all users in this section's group"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        if self.section_group:
            # Get users from all sections in the group
            return User.objects.filter(
                section__section_group=self.section_group,
                is_active=True
            )
        else:
            # Get users from this section and its subsections
            sections = [self] + self.get_all_subsections()
            return User.objects.filter(
                section__in=sections,
                is_active=True
            )
    
    def get_users_by_level(self, user_level_code):
        """Get users in this section's group by user level"""
        users = self.get_all_users_in_group()
        return users.filter(userlevel__code=user_level_code)
    
    def get_section_hierarchy(self):
        """Get the full hierarchy path for this section"""
        hierarchy = []
        current = self
        while current:
            hierarchy.insert(0, current)
            current = current.parent_section
        return hierarchy


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
    """Enhanced User model with better section grouping support"""
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
            models.Index(fields=['section__section_group']),  # For section group queries
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
    
    def get_section_group_users(self):
        """Get all users in the same section group"""
        if self.section and self.section.section_group:
            return User.objects.filter(
                section__section_group=self.section.section_group,
                is_active=True
            ).exclude(pk=self.pk)
        return User.objects.none()
    
    def get_section_group_users_by_level(self, user_level_code):
        """Get users in the same section group by user level"""
        users = self.get_section_group_users()
        return users.filter(userlevel__code=user_level_code)


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


# Manager classes for better querying
class SectionGroupManager(models.Manager):
    """Manager for SectionGroup with enhanced querying"""
    
    def with_user_counts(self):
        """Get section groups with user counts"""
        return self.annotate(
            total_users=models.Count('sections__users', filter=models.Q(sections__users__is_active=True)),
            section_chiefs=models.Count('sections__users', filter=models.Q(
                sections__users__is_active=True,
                sections__users__userlevel__code='Section Chief'
            )),
            unit_heads=models.Count('sections__users', filter=models.Q(
                sections__users__is_active=True,
                sections__users__userlevel__code='Unit Head'
            )),
            monitoring_personnel=models.Count('sections__users', filter=models.Q(
                sections__users__is_active=True,
                sections__users__userlevel__code='Monitoring Personnel'
            ))
        )
    
    def get_users_by_group(self, group_code):
        """Get all users in a specific section group"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return User.objects.filter(
            section__section_group__code=group_code,
            is_active=True
        )


class SectionManager(models.Manager):
    """Manager for Section with enhanced querying"""
    
    def with_user_counts(self):
        """Get sections with user counts"""
        return self.annotate(
            total_users=models.Count('users', filter=models.Q(users__is_active=True)),
            section_chiefs=models.Count('users', filter=models.Q(
                users__is_active=True,
                users__userlevel__code='Section Chief'
            )),
            unit_heads=models.Count('users', filter=models.Q(
                users__is_active=True,
                users__userlevel__code='Unit Head'
            )),
            monitoring_personnel=models.Count('users', filter=models.Q(
                users__is_active=True,
                users__userlevel__code='Monitoring Personnel'
            ))
        )
    
    def get_hierarchy(self):
        """Get sections with their hierarchy"""
        return self.select_related('parent_section', 'section_group').prefetch_related('subsections')


# Add managers to models
SectionGroup.objects = SectionGroupManager()
Section.objects = SectionManager()
