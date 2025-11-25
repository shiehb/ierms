"""
Enhanced email utilities for IERMS notification system
"""
import time
import logging
from typing import List, Dict, Any, Optional
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.contrib.auth import get_user_model
from django.utils import timezone

logger = logging.getLogger(__name__)
User = get_user_model()


class EmailValidationError(Exception):
    """Custom exception for email validation errors"""
    pass


class EmailDeliveryError(Exception):
    """Custom exception for email delivery errors"""
    pass


class EnhancedEmailService:
    """
    Enhanced email service with validation, retry logic, and comprehensive logging
    """
    
    def __init__(self):
        self.max_retries = getattr(settings, 'EMAIL_RETRY_ATTEMPTS', 3)
        self.retry_delay = getattr(settings, 'EMAIL_RETRY_DELAY', 5)
        self.subject_prefix = getattr(settings, 'EMAIL_SUBJECT_PREFIX', '[IERMS] ')
    
    def validate_email_address(self, email: str) -> bool:
        """
        Validate email address format and domain
        """
        try:
            validate_email(email)
            return True
        except ValidationError:
            raise EmailValidationError(f"Invalid email address format: {email}")
    
    def validate_email_context(self, context: Dict[str, Any]) -> bool:
        """
        Validate email context data
        """
        required_fields = ['recipient_email', 'subject', 'template_name']
        for field in required_fields:
            if field not in context:
                raise EmailValidationError(f"Missing required field: {field}")
        
        # Validate recipient email
        self.validate_email_address(context['recipient_email'])
        
        return True
    
    def get_email_headers(self, email_type: str = 'default') -> Dict[str, str]:
        """
        Get appropriate email headers based on email type
        """
        base_headers = getattr(settings, 'EMAIL_HEADERS', {})
        
        # Add type-specific headers
        type_headers = {
            'security': {
                'X-Priority': '1',
                'X-MSMail-Priority': 'High',
                'X-Mailer': 'IERMS Security System'
            },
            'inspection': {
                'X-Priority': '2',
                'X-MSMail-Priority': 'Normal',
                'X-Mailer': 'IERMS Inspection System'
            },
            'system': {
                'X-Priority': '3',
                'X-MSMail-Priority': 'Normal',
                'X-Mailer': 'IERMS System Notifications'
            }
        }
        
        headers = base_headers.copy()
        if email_type in type_headers:
            headers.update(type_headers[email_type])
        
        return headers
    
    def render_email_template(self, template_name: str, context: Dict[str, Any]) -> tuple:
        """
        Render email template and return both HTML and plain text versions
        """
        try:
            # Render HTML template
            html_message = render_to_string(template_name, context)
            
            # Create plain text version by stripping HTML tags
            from django.utils.html import strip_tags
            plain_message = strip_tags(html_message)
            
            # Clean up plain text formatting
            import re
            plain_message = re.sub(r'\n\s*\n', '\n\n', plain_message)
            plain_message = plain_message.strip()
            
            return html_message, plain_message
            
        except Exception as e:
            logger.error(f"Error rendering email template {template_name}: {str(e)}")
            raise EmailDeliveryError(f"Failed to render email template: {str(e)}")
    
    def send_email_with_retry(self, 
                            recipient_email: str,
                            subject: str,
                            html_message: str,
                            plain_message: str = None,
                            email_type: str = 'default',
                            context: Dict[str, Any] = None) -> bool:
        """
        Send email with retry logic and comprehensive error handling
        """
        context = context or {}
        
        # Add subject prefix
        if not subject.startswith(self.subject_prefix):
            subject = f"{self.subject_prefix}{subject}"
        
        # Get appropriate headers
        headers = self.get_email_headers(email_type)
        
        # Get sender email
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None)
        
        # Try to send email with retry logic
        last_exception = None
        
        for attempt in range(1, self.max_retries + 1):
            try:
                # Create email message
                email = EmailMultiAlternatives(
                    subject=subject,
                    body=plain_message or '',
                    from_email=from_email,
                    to=[recipient_email],
                    headers=headers
                )
                
                # Attach HTML version
                email.attach_alternative(html_message, "text/html")
                
                # Send email
                email.send(fail_silently=False)
                
                # Log successful delivery
                logger.info(f"Email sent successfully to {recipient_email} (attempt {attempt})")
                return True
                
            except Exception as e:
                last_exception = e
                logger.warning(f"Email delivery attempt {attempt} failed for {recipient_email}: {str(e)}")
                
                # Wait before retry (except on last attempt)
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)
        
        # All retry attempts failed
        logger.error(f"Email delivery failed after {self.max_retries} attempts for {recipient_email}")
        raise EmailDeliveryError(f"Failed to deliver email after {self.max_retries} attempts: {str(last_exception)}")
    
    def send_template_email(self, 
                          template_name: str,
                          recipient_email: str,
                          subject: str,
                          context: Dict[str, Any] = None,
                          email_type: str = 'default') -> bool:
        """
        Send email using Django template with full validation and error handling
        """
        context = context or {}
        
        try:
            # Validate inputs
            self.validate_email_address(recipient_email)
            
            # Add common context variables
            context.update({
                'site_name': getattr(settings, 'SITE_NAME', 'IERMS'),
                'site_url': getattr(settings, 'SITE_URL', 'https://ierms.denr.gov.ph'),
                'support_email': getattr(settings, 'SUPPORT_EMAIL', 'support@ierms.denr.gov.ph'),
                'current_year': timezone.now().year,
                'current_time': timezone.now(),
            })
            
            # Render templates
            html_message, plain_message = self.render_email_template(template_name, context)
            
            # Send email
            return self.send_email_with_retry(
                recipient_email=recipient_email,
                subject=subject,
                html_message=html_message,
                plain_message=plain_message,
                email_type=email_type,
                context=context
            )
            
        except (EmailValidationError, EmailDeliveryError) as e:
            logger.error(f"Email service error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in email service: {str(e)}")
            raise EmailDeliveryError(f"Unexpected error: {str(e)}")


# Convenience functions for common email types
def send_security_alert(user: User, alert_type: str, **kwargs) -> bool:
    """
    Send security alert email to user
    """
    service = EnhancedEmailService()
    
    context = {
        'user': user,
        'alert_type': alert_type,
        'ip_address': kwargs.get('ip_address'),
        'user_agent': kwargs.get('user_agent'),
        'location': kwargs.get('location'),
        'failed_attempts': kwargs.get('failed_attempts'),
        'lockout_duration': kwargs.get('lockout_duration'),
        'reset_password_url': kwargs.get('reset_password_url', f"{getattr(settings, 'SITE_URL', 'https://ierms.denr.gov.ph')}/reset-password"),
        'login_url': kwargs.get('login_url', f"{getattr(settings, 'SITE_URL', 'https://ierms.denr.gov.ph')}/login"),
    }
    
    subject = f"Security Alert: {alert_type.replace('_', ' ').title()}"
    
    return service.send_template_email(
        template_name='emails/security_alert.html',
        recipient_email=user.email,
        subject=subject,
        context=context,
        email_type='security'
    )


def send_inspection_assignment(inspector: User, inspection, establishment, **kwargs) -> bool:
    """
    Send inspection assignment email to inspector
    """
    service = EnhancedEmailService()
    
    context = {
        'inspector': inspector,
        'inspection': inspection,
        'establishment': establishment,
        'assigned_by': kwargs.get('assigned_by'),
        'supervisor': kwargs.get('supervisor'),
        'inspection_url': kwargs.get('inspection_url', f"{getattr(settings, 'SITE_URL', 'https://ierms.denr.gov.ph')}/inspections/{inspection.id if inspection else 'new'}"),
        'establishment_url': kwargs.get('establishment_url', f"{getattr(settings, 'SITE_URL', 'https://ierms.denr.gov.ph')}/establishments/{establishment.id if establishment else 'new'}"),
    }
    
    subject = f"Inspection Assignment: {establishment.name if establishment else 'New Inspection'}"
    
    return service.send_template_email(
        template_name='emails/inspection_assignment.html',
        recipient_email=inspector.email,
        subject=subject,
        context=context,
        email_type='inspection'
    )


def send_welcome_email(user: User, default_password: str, **kwargs) -> bool:
    """
    Send welcome email to new user
    """
    service = EnhancedEmailService()
    
    context = {
        'user': user,
        'default_password': default_password,
        'login_url': kwargs.get('login_url', f"{getattr(settings, 'SITE_URL', 'https://ierms.denr.gov.ph')}/login"),
    }
    
    subject = "Account Activation - IERMS Access Credentials"
    
    return service.send_template_email(
        template_name='emails/welcome_email.html',
        recipient_email=user.email,
        subject=subject,
        context=context,
        email_type='system'
    )


def send_otp_email(user: User, otp_code: str, **kwargs) -> bool:
    """
    Send OTP email to user
    """
    service = EnhancedEmailService()
    
    context = {
        'user': user,
        'otp_code': otp_code,
        'ip_address': kwargs.get('ip_address'),
    }
    
    subject = "Password Reset Verification Code"
    
    return service.send_template_email(
        template_name='emails/otp_email.html',
        recipient_email=user.email,
        subject=subject,
        context=context,
        email_type='security'
    )


def get_device_type(user_agent_string: str) -> str:
    """
    Detect device type from User-Agent string
    Returns: 'Desktop', 'Tablet', or 'Mobile'
    """
    if not user_agent_string:
        return 'Unknown'
    
    user_agent = user_agent_string.lower()
    
    # Check for mobile devices
    mobile_keywords = ['mobile', 'android', 'iphone', 'ipod', 'blackberry', 'windows phone', 'webos']
    # Check for tablets
    tablet_keywords = ['tablet', 'ipad', 'playbook', 'kindle']
    
    # Check tablets first (as some tablets may also contain 'mobile' in UA)
    if any(keyword in user_agent for keyword in tablet_keywords):
        return 'Tablet'
    
    # Then check for mobile
    if any(keyword in user_agent for keyword in mobile_keywords):
        return 'Mobile'
    
    # Default to desktop
    return 'Desktop'


def send_account_activated_email(user: User, activated_by: User, **kwargs) -> bool:
    """
    Send account activation notification email to user
    """
    try:
        service = EnhancedEmailService()
        
        # Get device type from user agent if provided
        user_agent = kwargs.get('user_agent', '')
        device_type = get_device_type(user_agent)
        
        context = {
            'user': user,
            'activated_by': activated_by,
            'login_url': kwargs.get('login_url', f"{getattr(settings, 'SITE_URL', 'https://ierms.denr.gov.ph')}/login"),
            'device_type': device_type,
            'ip_address': kwargs.get('ip_address', 'Not available'),
        }
        
        subject = "Account Activated - IERMS Access Restored"
        
        return service.send_template_email(
            template_name='emails/account_activated.html',
            recipient_email=user.email,
            subject=subject,
            context=context,
            email_type='system'
        )
    except Exception as e:
        logger.error(f"Failed to send account activation email to {user.email}: {str(e)}")
        return False


def send_account_deactivated_email(user: User, deactivated_by: User, **kwargs) -> bool:
    """
    Send account deactivation notification email to user
    """
    try:
        service = EnhancedEmailService()
        
        # Get device type from user agent if provided
        user_agent = kwargs.get('user_agent', '')
        device_type = get_device_type(user_agent)
        
        context = {
            'user': user,
            'deactivated_by': deactivated_by,
            'support_email': kwargs.get('support_email', 'support@ierms.denr.gov.ph'),
            'device_type': device_type,
            'ip_address': kwargs.get('ip_address', 'Not available'),
        }
        
        subject = "Account Deactivated - IERMS Access Suspended"
        
        return service.send_template_email(
            template_name='emails/account_deactivated.html',
            recipient_email=user.email,
            subject=subject,
            context=context,
            email_type='system'
        )
    except Exception as e:
        logger.error(f"Failed to send account deactivation email to {user.email}: {str(e)}")
        return False