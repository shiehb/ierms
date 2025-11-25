                                                                                                # users/models.py (updated)
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone
from django.conf import settings
from core.settings import generate_secure_password

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, password_provided=False, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        if not password:
            # Use auto-generated password
            password = generate_secure_password()
        
        # Set must_change_password=True by default for new users (unless explicitly set)
        if 'must_change_password' not in extra_fields:
            extra_fields['must_change_password'] = True
        
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
        extra_fields.setdefault('userlevel', 'Admin')  # Auto-set Admin level
        extra_fields.setdefault('first_name', 'Administrator')  # Auto-set first name
        extra_fields.setdefault('is_first_login', False)  # Not first login
        extra_fields.setdefault('must_change_password', False)  # No password change required
        # Don't send welcome email for superuser - password is provided by admin
        return self.create_user(email, password, password_provided=True, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    USERLEVEL_CHOICES = [
        ("Admin", "Admin"),
        ("Legal Unit", "Legal Unit"),
        ("Division Chief", "Division Chief"),
        ("Section Chief", "Section Chief"),
        ("Unit Head", "Unit Head"),
        ("Monitoring Personnel", "Monitoring Personnel"),
    ]

    SECTION_CHOICES = [
        ("RA-6969", "RA-6969"),
        ("RA-8749", "RA-8749"),
        ("RA-9275", "RA-9275"),
        ("RA-9003", "RA-9003"),
        ("PD-1586", "PD-1586"),
        ("PD-1586,RA-8749,RA-9275", "EIA, Air & Water (Combined)"),
    ]

    email = models.EmailField(unique=True, max_length=255)
    first_name = models.CharField(max_length=150, blank=True)
    middle_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    userlevel = models.CharField(max_length=50, choices=USERLEVEL_CHOICES, blank=True)
    section = models.CharField(max_length=50, choices=SECTION_CHOICES, null=True, blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)


    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)  # NEW: Auto-update timestamp
    is_first_login = models.BooleanField(default=True)
    must_change_password = models.BooleanField(default=False)
    
    # Security fields for login attempt tracking
    failed_login_attempts = models.PositiveIntegerField(default=0)
    last_failed_login = models.DateTimeField(null=True, blank=True)
    account_locked_until = models.DateTimeField(null=True, blank=True)
    is_account_locked = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return f"{self.email} ({self.userlevel})"

    def save(self, *args, **kwargs):
        # Update the updated_at field on every save
        if self.pk:  # Only update if the object already exists
            self.updated_at = timezone.now()
        super().save(*args, **kwargs)
    
    DEFAULT_MAX_FAILED_LOGIN_ATTEMPTS = 10
    DEFAULT_LOCKOUT_DURATION_MINUTES = 3

    def increment_failed_login(self):
        """Increment failed login attempts and handle account locking"""
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        
        # If the previous failed attempt is stale, restart the counter
        if self.last_failed_login and now - self.last_failed_login > timedelta(minutes=self.lockout_duration_minutes):
            self.failed_login_attempts = 1
        else:
            self.failed_login_attempts += 1
        
        self.last_failed_login = now
        
        # Lock account after configured number of failed attempts
        if self.failed_login_attempts >= self.max_failed_login_attempts:
            self.is_account_locked = True
            self.account_locked_until = now + timedelta(minutes=self.lockout_duration_minutes)
            
        self.save(update_fields=['failed_login_attempts', 'last_failed_login', 'is_account_locked', 'account_locked_until'])
        
        # Send security alert if multiple failed attempts
        if self.failed_login_attempts >= 3:
            self.send_security_alert('failed_login', failed_attempts=self.failed_login_attempts)
        
        # Send account lockout alert
        if self.is_account_locked:
            self.send_security_alert('account_lockout', lockout_duration=self.lockout_duration_minutes)

    @property
    def max_failed_login_attempts(self):
        return getattr(settings, 'LOGIN_MAX_FAILED_ATTEMPTS', self.DEFAULT_MAX_FAILED_LOGIN_ATTEMPTS)

    @property
    def lockout_duration_minutes(self):
        return getattr(settings, 'LOGIN_LOCKOUT_DURATION_MINUTES', self.DEFAULT_LOCKOUT_DURATION_MINUTES)
    
    def reset_failed_logins(self):
        """Reset failed login attempts on successful login"""
        if self.failed_login_attempts > 0:
            self.failed_login_attempts = 0
            self.is_account_locked = False
            self.account_locked_until = None
            self.save(update_fields=['failed_login_attempts', 'is_account_locked', 'account_locked_until'])
    
    def is_account_currently_locked(self):
        """Check if account is currently locked"""
        from django.utils import timezone
        
        if not self.is_account_locked:
            return False
            
        if self.account_locked_until and timezone.now() > self.account_locked_until:
            # Auto-unlock expired account
            self.failed_login_attempts = 0
            self.is_account_locked = False
            self.account_locked_until = None
            self.save(update_fields=['failed_login_attempts', 'is_account_locked', 'account_locked_until'])
            return False
            
        return True
    
    def send_security_alert(self, alert_type, **kwargs):
        """Send security alert email"""
        try:
            from .utils.email_utils import send_security_alert
            
            send_security_alert(
                user=self,
                alert_type=alert_type,
                ip_address=kwargs.get('ip_address'),
                user_agent=kwargs.get('user_agent'),
                location=kwargs.get('location'),
                failed_attempts=kwargs.get('failed_attempts'),
                lockout_duration=kwargs.get('lockout_duration')
            )
        except Exception as e:
            print(f"Failed to send security alert: {e}")

    class Meta:
        indexes = [
            models.Index(fields=['first_name', 'last_name']),
            models.Index(fields=['email']),
            models.Index(fields=['userlevel']),
        ]