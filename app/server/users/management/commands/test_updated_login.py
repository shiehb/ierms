from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
import json

User = get_user_model()

class Command(BaseCommand):
    help = 'Test the updated login system with proper error notifications'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            help='Email address to test with',
            default='test@example.com'
        )
        parser.add_argument(
            '--password',
            type=str,
            help='Password to test with',
            default='wrongpassword123'
        )

    def handle(self, *args, **options):
        email_address = options['email']
        password = options['password']
        
        self.stdout.write("🔐 Testing Updated Login System...")
        self.stdout.write("=" * 60)
        
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
            test_user.set_password('correctpassword123')
            test_user.save()
            self.stdout.write(f"✅ Created test user: {test_user.email}")
            self.stdout.write(f"   Correct password: correctpassword123")
        else:
            self.stdout.write(f"✅ Using existing user: {test_user.email}")
        
        # Reset any existing failed attempts
        test_user.failed_login_attempts = 0
        test_user.is_account_locked = False
        test_user.account_locked_until = None
        test_user.save()
        
        self.stdout.write(f"📊 Initial failed attempts: {test_user.failed_login_attempts}")
        self.stdout.write(f"🔒 Account locked: {test_user.is_account_locked}")
        
        # Test login attempts using the new API endpoint
        client = Client()
        login_url = '/api/auth/login/'
        
        self.stdout.write("\n🎭 Testing Login Error Responses...")
        self.stdout.write("-" * 40)
        
        # Test 1: Missing credentials
        self.stdout.write(f"\n🔄 Test 1: Missing credentials...")
        response = client.post(
            login_url,
            data=json.dumps({}),
            content_type='application/json'
        )
        response_data = response.json()
        self.stdout.write(f"   📊 Status Code: {response.status_code}")
        self.stdout.write(f"   📧 Error Code: {response_data.get('error_code', 'None')}")
        self.stdout.write(f"   📧 Error Message: {response_data.get('error', 'None')}")
        
        # Test 2: Invalid credentials
        self.stdout.write(f"\n🔄 Test 2: Invalid credentials...")
        response = client.post(
            login_url,
            data=json.dumps({
                'email': email_address,
                'password': password
            }),
            content_type='application/json'
        )
        response_data = response.json()
        self.stdout.write(f"   📊 Status Code: {response.status_code}")
        self.stdout.write(f"   📧 Error Code: {response_data.get('error_code', 'None')}")
        self.stdout.write(f"   📧 Error Message: {response_data.get('error', 'None')}")
        
        # Test 3: Simulate account lockout
        self.stdout.write(f"\n🔄 Test 3: Simulating account lockout...")
        
        # Manually set failed attempts to trigger lockout
        test_user.failed_login_attempts = 5
        test_user.is_account_locked = True
        from django.utils import timezone
        from datetime import timedelta
        test_user.account_locked_until = timezone.now() + timedelta(minutes=15)
        test_user.save()
        
        response = client.post(
            login_url,
            data=json.dumps({
                'email': email_address,
                'password': password
            }),
            content_type='application/json'
        )
        response_data = response.json()
        self.stdout.write(f"   📊 Status Code: {response.status_code}")
        self.stdout.write(f"   📧 Error Code: {response_data.get('error_code', 'None')}")
        self.stdout.write(f"   📧 Error Message: {response_data.get('error', 'None')}")
        
        if 'details' in response_data:
            details = response_data['details']
            self.stdout.write(f"   🔒 Locked Until: {details.get('locked_until', 'None')}")
            self.stdout.write(f"   ⏰ Remaining Minutes: {details.get('remaining_minutes', 'None')}")
            self.stdout.write(f"   🔢 Failed Attempts: {details.get('failed_attempts', 'None')}")
        
        # Test 4: Successful login (reset lockout first)
        self.stdout.write(f"\n🔄 Test 4: Successful login...")
        
        # Reset lockout
        test_user.failed_login_attempts = 0
        test_user.is_account_locked = False
        test_user.account_locked_until = None
        test_user.save()
        
        response = client.post(
            login_url,
            data=json.dumps({
                'email': email_address,
                'password': 'correctpassword123'
            }),
            content_type='application/json'
        )
        
        self.stdout.write(f"   📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            response_data = response.json()
            self.stdout.write(f"   ✅ Success: {response_data.get('success', 'None')}")
            self.stdout.write(f"   📧 Message: {response_data.get('message', 'None')}")
            if 'user' in response_data:
                user_data = response_data['user']
                self.stdout.write(f"   👤 User: {user_data.get('email', 'None')}")
            if 'tokens' in response_data:
                self.stdout.write(f"   🔑 Tokens provided: Yes")
        else:
            response_data = response.json()
            self.stdout.write(f"   ❌ Failed: {response_data}")
        
        # Test 5: Account deactivated
        self.stdout.write(f"\n🔄 Test 5: Account deactivated...")
        
        test_user.is_active = False
        test_user.save()
        
        response = client.post(
            login_url,
            data=json.dumps({
                'email': email_address,
                'password': 'correctpassword123'
            }),
            content_type='application/json'
        )
        response_data = response.json()
        self.stdout.write(f"   📊 Status Code: {response.status_code}")
        self.stdout.write(f"   📧 Error Code: {response_data.get('error_code', 'None')}")
        self.stdout.write(f"   📧 Error Message: {response_data.get('error', 'None')}")
        
        # Reset account status
        test_user.is_active = True
        test_user.save()
        
        # Final status
        test_user.refresh_from_db()
        self.stdout.write(f"\n📊 Final Status:")
        self.stdout.write(f"   🔢 Failed attempts: {test_user.failed_login_attempts}")
        self.stdout.write(f"   🔒 Account locked: {test_user.is_account_locked}")
        self.stdout.write(f"   ✅ Account active: {test_user.is_active}")
        
        self.stdout.write(f"\n✅ Updated Login System Test Complete!")
        self.stdout.write(f"\n💡 New Error Response Features:")
        self.stdout.write(f"   🔒 ACCOUNT_LOCKED: HTTP 423 with detailed lockout info")
        self.stdout.write(f"   ❌ INVALID_CREDENTIALS: HTTP 401 with clear message")
        self.stdout.write(f"   🚫 ACCOUNT_DEACTIVATED: HTTP 403 with admin contact info")
        self.stdout.write(f"   📝 MISSING_CREDENTIALS: HTTP 400 with field requirements")
        self.stdout.write(f"   ✅ SUCCESS: HTTP 200 with user data and tokens")
        
        self.stdout.write(f"\n🎯 Frontend Integration:")
        self.stdout.write(f"   📧 Required field indicators: Added red asterisks (*)")
        self.stdout.write(f"   🔒 Account lockout UI: Special styling and countdown")
        self.stdout.write(f"   📱 Notification actions: Contact support buttons")
        self.stdout.write(f"   🎨 Error styling: Different colors for different error types")
