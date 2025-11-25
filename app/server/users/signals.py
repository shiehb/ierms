from django.db.models.signals import post_save
from django.dispatch import receiver, Signal
from django.conf import settings
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.utils import timezone
from .models import User
from .utils.email_utils import send_welcome_email, send_security_alert
from audit.constants import AUDIT_ACTIONS, AUDIT_MODULES
from audit.utils import log_activity

# Custom signal for user creation with password
user_created_with_password = Signal()

# 🔹 User created or updated
@receiver(post_save, sender=User)
def log_user_activity(sender, instance, created, **kwargs):
    if created:
        # Log user creation
        log_activity(
            instance,
            AUDIT_ACTIONS["CREATE"],
            module=AUDIT_MODULES["USERS"],
            description=f"User account created: {instance.email}",
            metadata={
                "entity_name": instance.email,
                "entity_id": instance.id,
                "role": instance.userlevel,
                "status": "success",
            },
        )
    else:
        # Log user update
        log_activity(
            instance,
            AUDIT_ACTIONS["UPDATE"],
            module=AUDIT_MODULES["USERS"],
            description=f"User account updated: {instance.email}",
            metadata={
                "entity_name": instance.email,
                "entity_id": instance.id,
                "status": "success",
            },
        )

# 🔹 Handle user creation with password
@receiver(user_created_with_password)
def send_welcome_email_on_creation(sender, user, password, **kwargs):
    """Send welcome email when user is created with a specific password"""
    send_welcome_email(user, password)


# 🔹 Log successful login
@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    # Reset failed login attempts on successful login
    user.reset_failed_logins()
    
    log_activity(
        user,
        AUDIT_ACTIONS["LOGIN"],
        module=AUDIT_MODULES["AUTH"],
        description=f"User {user.email} logged in successfully",
        metadata={
            "user_id": user.id,
            "email": user.email,
            "status": "success",
        },
        request=request,
    )


# 🔹 Log logout
@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    log_activity(
        user,
        AUDIT_ACTIONS["LOGOUT"],
        module=AUDIT_MODULES["AUTH"],
        description=f"User {user.email} logged out",
        metadata={
            "user_id": user.id,
            "email": user.email,
            "status": "success",
        },
        request=request,
    )


# 🔹 Handle failed login attempts
@receiver(user_login_failed)
def handle_failed_login(sender, credentials, request, **kwargs):
    """Handle failed login attempts and send security alerts"""
    email = credentials.get('email') or credentials.get('username')
    
    if email:
        try:
            user = User.objects.get(email=email)
            
            # Get request information
            ip_address = get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
            
            # Increment failed login attempts
            user.increment_failed_login()
            
            # Log the failed attempt
            log_activity(
                user,
                AUDIT_ACTIONS["LOGIN"],
                module=AUDIT_MODULES["AUTH"],
                description=f"Failed login attempt for {user.email} (attempt #{user.failed_login_attempts})",
                metadata={
                    "user_id": user.id,
                    "email": user.email,
                    "status": "failed",
                    "reason": "invalid_credentials",
                    "attempt": user.failed_login_attempts,
                    "ip": ip_address,
                    "user_agent": user_agent,
                },
                request=request,
            )
            
        except User.DoesNotExist:
            # Log failed attempt for non-existent user
            log_activity(
                None,
                AUDIT_ACTIONS["LOGIN"],
                module=AUDIT_MODULES["AUTH"],
                description=f"Failed login attempt for non-existent user: {email}",
                metadata={
                    "email": email,
                    "status": "failed",
                    "reason": "invalid_credentials",
                    "ip": get_client_ip(request),
                },
                request=request,
            )


def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip