from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.contrib.auth import get_user_model
from users.utils.email_utils import (
    send_security_alert, 
    send_inspection_assignment, 
    send_welcome_email, 
    send_otp_email,
    EnhancedEmailService
)

User = get_user_model()

class Command(BaseCommand):
    help = 'Test email configuration and send test emails'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            help='Email address to send test email to',
            default='test@example.com'
        )
        parser.add_argument(
            '--type',
            type=str,
            choices=['welcome', 'otp', 'security', 'inspection', 'all'],
            help='Type of email template to test',
            default='welcome'
        )
        parser.add_argument(
            '--enhanced',
            action='store_true',
            help='Use enhanced email service',
            default=True
        )

    def handle(self, *args, **options):
        email_address = options['email']
        email_type = options['type']
        use_enhanced = options['enhanced']
        
        self.stdout.write(f"Testing email configuration...")
        self.stdout.write(f"Email Backend: {settings.EMAIL_BACKEND}")
        self.stdout.write(f"Email Host: {settings.EMAIL_HOST}")
        self.stdout.write(f"Email Port: {settings.EMAIL_PORT}")
        self.stdout.write(f"From Email: {settings.DEFAULT_FROM_EMAIL}")
        self.stdout.write(f"Using Enhanced Service: {use_enhanced}")
        
        # Create a test user for template rendering
        test_user, created = User.objects.get_or_create(
            email=email_address,
            defaults={
                'first_name': 'Test',
                'last_name': 'User',
                'userlevel': 'Inspector',
                'section': 'PD-1586',
                'district': 'La Union - 1st'
            }
        )
        
        # Create mock objects for testing
        mock_establishment = type('Establishment', (), {
            'id': 1,
            'name': 'Test Restaurant & Bar',
            'establishment_type': 'Food Service',
            'address': '123 Test Street, San Fernando City, La Union'
        })()
        
        mock_inspection = type('Inspection', (), {
            'id': 1,
            'code': 'INS-2025-001',
            'inspection_type': 'Regular Inspection',
            'scheduled_date': '2025-01-15',
            'scheduled_time': '9:00 AM',
            'priority': 'high',
            'notes': 'Test inspection with special requirements'
        })()
        
        mock_supervisor = type('Supervisor', (), {
            'name': 'John Doe',
            'phone': '+63 912 345 6789'
        })()
        
        try:
            if email_type == 'welcome' or email_type == 'all':
                self.stdout.write("Testing welcome email...")
                if use_enhanced:
                    success = send_welcome_email(test_user, 'TempPass123!', login_url='http://localhost:3000/login')
                else:
                    success = self._send_legacy_welcome_email(test_user, email_address)
                self._report_result('welcome', email_address, success)
                
            if email_type == 'otp' or email_type == 'all':
                self.stdout.write("Testing OTP email...")
                if use_enhanced:
                    success = send_otp_email(test_user, '123456', ip_address='192.168.1.1')
                else:
                    success = self._send_legacy_otp_email(test_user, email_address)
                self._report_result('OTP', email_address, success)
                
            if email_type == 'security' or email_type == 'all':
                self.stdout.write("Testing security alert email...")
                success = send_security_alert(
                    test_user, 
                    'failed_login',
                    ip_address='192.168.1.100',
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                    location='San Fernando City, La Union',
                    failed_attempts=3
                )
                self._report_result('security alert', email_address, success)
                
            if email_type == 'inspection' or email_type == 'all':
                self.stdout.write("Testing inspection assignment email...")
                success = send_inspection_assignment(
                    test_user,
                    mock_inspection,
                    mock_establishment,
                    assigned_by={'name': 'System Administrator'},
                    supervisor=mock_supervisor
                )
                self._report_result('inspection assignment', email_address, success)
            
            if settings.EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend':
                self.stdout.write(
                    self.style.WARNING('⚠️  Emails were printed to console (console backend active)')
                )
                self.stdout.write('   To send real emails, configure EMAIL_HOST_USER and EMAIL_HOST_PASSWORD')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error sending test email: {str(e)}')
            )
    
    def _report_result(self, email_type, email_address, success):
        """Report the result of email sending"""
        if success:
            self.stdout.write(
                self.style.SUCCESS(f'✅ Test {email_type} email sent successfully to {email_address}')
            )
        else:
            self.stdout.write(
                self.style.ERROR(f'❌ Failed to send test {email_type} email to {email_address}')
            )
    
    def _send_legacy_welcome_email(self, user, email_address):
        """Legacy welcome email method"""
        try:
            html_message = render_to_string('emails/welcome_email.html', {
                'user': user,
                'default_password': 'TempPass123!',
                'login_url': 'http://localhost:3000/login'
            })
            
            send_mail(
                subject='IERMS Account Activation - Test Email',
                message='',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email_address],
                html_message=html_message,
                fail_silently=False
            )
            return True
        except Exception as e:
            print(f"Error sending legacy welcome email: {e}")
            return False
    
    def _send_legacy_otp_email(self, user, email_address):
        """Legacy OTP email method"""
        try:
            html_message = render_to_string('emails/otp_email.html', {
                'user': user,
                'otp_code': '123456',
                'ip_address': '192.168.1.1',
                'email': user.email
            })
            
            send_mail(
                subject='IERMS Password Reset - Test Email',
                message='',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email_address],
                html_message=html_message,
                fail_silently=False
            )
            return True
        except Exception as e:
            print(f"Error sending legacy OTP email: {e}")
            return False
