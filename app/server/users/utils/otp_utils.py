import random
from django.core.cache import cache
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import os

def generate_otp(email):
    """Generate a 6-digit OTP and store it in cache"""
    otp = str(random.randint(100000, 999999))
    # Store OTP with email as key, valid for 10 minutes
    cache.set(f"otp_{email}", otp, timeout=600)
    return otp

def verify_otp(email, otp):
    """Verify if the provided OTP matches the stored one"""
    stored_otp = cache.get(f"otp_{email}")
    return stored_otp == otp

def send_otp_email(user_email, otp, user=None, ip_address=None):
    """Send OTP email to user using enhanced email service"""
    try:
        # Use the new enhanced email service
        from .email_utils import send_otp_email as enhanced_send_otp_email
        
        # Create user object if not provided
        if user is None:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                user = User.objects.get(email=user_email)
            except User.DoesNotExist:
                # Create a minimal user object for email template
                user = type('User', (), {
                    'email': user_email,
                    'first_name': '',
                    'last_name': ''
                })()
        
        return enhanced_send_otp_email(user, otp, ip_address=ip_address)
        
    except Exception as e:
        print(f"Error sending OTP email: {e}")
        # Fallback to original method if enhanced service fails
        return _send_otp_email_fallback(user_email, otp, user, ip_address)


def _send_otp_email_fallback(user_email, otp, user=None, ip_address=None):
    """Fallback OTP email method"""
    subject = 'Password Reset OTP'
    
    # Try to get the template path
    template_path = os.path.join(settings.BASE_DIR, 'users', 'templates', 'emails', 'otp_email.html')
    
    # Check if template exists, fallback to simple text
    if os.path.exists(template_path):
        html_message = render_to_string('emails/otp_email.html', {
            'otp_code': otp,
            'user': user,
            'email': user_email,
            'ip_address': ip_address,
            'logo_url': getattr(settings, 'EMAIL_HEADER_LOGO_URL', None),
            'logo_alt': getattr(settings, 'EMAIL_HEADER_LOGO_ALT', 'IERMS Logo'),
        })
        plain_message = strip_tags(html_message)
    else:
        # Fallback to simple text email if template not found
        plain_message = f"""
        Password Reset Request
        
        You requested a password reset. Here is your OTP code:
        
        {otp}
        
        This code will expire in 10 minutes.
        
        If you didn't request this reset, please ignore this email.
        """
        html_message = None
    
    try:
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None)
        if not from_email and SystemConfiguration is not None:
            try:
                from_email = SystemConfiguration.get_active_config().get_constructed_from_email()
            except Exception:
                from_email = None
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=from_email,
            recipient_list=[user_email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending OTP email: {e}")
        return False