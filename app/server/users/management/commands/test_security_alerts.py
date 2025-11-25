from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings
from users.utils.email_utils import send_security_alert

User = get_user_model()

class Command(BaseCommand):
    help = 'Test security alert emails and login attempt tracking'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            help='Email address to test with',
            default='test@example.com'
        )
        parser.add_argument(
            '--simulate-login-attempts',
            action='store_true',
            help='Simulate failed login attempts',
            default=False
        )

    def handle(self, *args, **options):
        email_address = options['email']
        simulate_attempts = options['simulate_login_attempts']
        
        self.stdout.write("🔐 Testing IERMS Security Alert System...")
        self.stdout.write("=" * 50)
        
        # Create or get test user
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
        
        if created:
            self.stdout.write(f"✅ Created test user: {test_user.email}")
        else:
            self.stdout.write(f"✅ Using existing user: {test_user.email}")
        
        self.stdout.write(f"📊 Current failed attempts: {test_user.failed_login_attempts}")
        self.stdout.write(f"🔒 Account locked: {test_user.is_account_locked}")

        max_failed_attempts = test_user.max_failed_login_attempts if hasattr(test_user, "max_failed_login_attempts") else getattr(settings, "LOGIN_MAX_FAILED_ATTEMPTS", 10)
        lockout_duration = test_user.lockout_duration_minutes if hasattr(test_user, "lockout_duration_minutes") else getattr(settings, "LOGIN_LOCKOUT_DURATION_MINUTES", 3)
        warning_threshold = getattr(settings, "LOGIN_FINAL_ATTEMPTS_WARNING", 3)
        
        # Test Security Alert Emails
        self.stdout.write("\n📧 Testing Security Alert Emails...")
        self.stdout.write("-" * 30)
        
        try:
            # Test 1: Failed Login Alert
            self.stdout.write("🚨 Testing Failed Login Alert...")
            success = send_security_alert(
                test_user,
                'failed_login',
                ip_address='192.168.1.100',
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                location='San Fernando City, La Union',
                failed_attempts=3
            )
            self._report_result('Failed Login Alert', success)
            
            # Test 2: Account Lockout Alert
            self.stdout.write("🔒 Testing Account Lockout Alert...")
            success = send_security_alert(
                test_user,
                'account_lockout',
                ip_address='192.168.1.100',
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                location='San Fernando City, La Union',
                lockout_duration=lockout_duration
            )
            self._report_result('Account Lockout Alert', success)
            
            # Test 3: Password Change Alert
            self.stdout.write("🔑 Testing Password Change Alert...")
            success = send_security_alert(
                test_user,
                'password_change',
                ip_address='192.168.1.100',
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                location='San Fernando City, La Union'
            )
            self._report_result('Password Change Alert', success)
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error testing security alerts: {str(e)}')
            )
        
        # Simulate Login Attempts
        if simulate_attempts:
            self.stdout.write("\n🎭 Simulating Failed Login Attempts...")
            self.stdout.write("-" * 40)
            
            # Reset user first
            test_user.failed_login_attempts = 0
            test_user.is_account_locked = False
            test_user.account_locked_until = None
            test_user.save()
            
            for attempt in range(1, max_failed_attempts + 2):
                self.stdout.write(f"Attempt {attempt}: Simulating failed login...")
                test_user.increment_failed_login()
                
                self.stdout.write(f"  📊 Failed attempts: {test_user.failed_login_attempts}")
                self.stdout.write(f"  🔒 Account locked: {test_user.is_account_locked}")
                
                if test_user.is_account_locked:
                    self.stdout.write(f"  ⏰ Locked until: {test_user.account_locked_until}")
                    break
                
                # Small delay for readability
                import time
                time.sleep(1)
        
        # Display Current Security Status
        self.stdout.write("\n📊 Current Security Status:")
        self.stdout.write("-" * 30)
        test_user.refresh_from_db()
        self.stdout.write(f"📧 Email: {test_user.email}")
        self.stdout.write(f"🔢 Failed attempts: {test_user.failed_login_attempts}")
        self.stdout.write(f"🔒 Account locked: {test_user.is_account_locked}")
        self.stdout.write(f"⏰ Last failed login: {test_user.last_failed_login}")
        if test_user.is_account_locked:
            self.stdout.write(f"⏰ Locked until: {test_user.account_locked_until}")
        
        # Security Configuration Summary
        self.stdout.write("\n⚙️ Security Configuration:")
        self.stdout.write("-" * 30)
        self.stdout.write(f"🔢 Max failed attempts: {max_failed_attempts}")
        self.stdout.write(f"⏰ Lockout duration: {lockout_duration} minutes")
        self.stdout.write(f"📧 Alert threshold: {warning_threshold} attempts")
        self.stdout.write("🔄 Auto-unlock: Yes")
        
        self.stdout.write("\n✅ Security Alert System Test Complete!")
        
        if simulate_attempts:
            self.stdout.write("\n💡 To reset the test user:")
            self.stdout.write(f"   test_user.reset_failed_logins()")

    def _report_result(self, test_name, success):
        """Report the result of a test"""
        if success:
            self.stdout.write(
                self.style.SUCCESS(f'  ✅ {test_name} sent successfully')
            )
        else:
            self.stdout.write(
                self.style.ERROR(f'  ❌ {test_name} failed to send')
            )
