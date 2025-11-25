from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
import json

User = get_user_model()

class Command(BaseCommand):
    help = 'Test account lockout error notifications'

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
        
        self.stdout.write("🔐 Testing Account Lockout Error Notifications...")
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
        
        # Test login attempts using the API
        client = Client()
        login_url = '/api/auth/login/'
        
        self.stdout.write("\n🎭 Testing Failed Login Attempts...")
        self.stdout.write("-" * 40)
        
        for attempt in range(1, 8):
            self.stdout.write(f"\n🔄 Attempt {attempt}: Testing login with wrong password...")
            
            # Make login request
            response = client.post(
                login_url,
                data=json.dumps({
                    'email': email_address,
                    'password': password
                }),
                content_type='application/json'
            )
            
            # Parse response
            try:
                response_data = response.json()
            except:
                response_data = {'error': 'Invalid JSON response'}
            
            self.stdout.write(f"   📊 Status Code: {response.status_code}")
            self.stdout.write(f"   📧 Response: {response_data}")
            
            # Refresh user data
            test_user.refresh_from_db()
            self.stdout.write(f"   🔢 Failed attempts: {test_user.failed_login_attempts}")
            self.stdout.write(f"   🔒 Account locked: {test_user.is_account_locked}")
            
            # Check for specific error responses
            if 'error_code' in response_data:
                error_code = response_data['error_code']
                
                if error_code == 'ACCOUNT_LOCKED':
                    self.stdout.write(f"   🚨 ACCOUNT LOCKED ERROR DETECTED!")
                    self.stdout.write(f"   ⏰ Locked until: {response_data.get('details', {}).get('locked_until', 'Unknown')}")
                    self.stdout.write(f"   ⏳ Remaining minutes: {response_data.get('details', {}).get('remaining_minutes', 'Unknown')}")
                    self.stdout.write(f"   📧 Message: {response_data.get('message', 'No message')}")
                    break
                elif error_code == 'INVALID_CREDENTIALS':
                    self.stdout.write(f"   ❌ Invalid credentials (expected)")
                else:
                    self.stdout.write(f"   ⚠️ Unexpected error code: {error_code}")
            
            if attempt >= 5:
                self.stdout.write(f"   🎯 Expected account lockout after 5 attempts")
        
        # Test successful login after lockout period
        self.stdout.write(f"\n✅ Testing successful login with correct password...")
        
        # First, simulate that lockout period has expired
        if test_user.is_account_locked:
            self.stdout.write(f"   🔓 Simulating lockout period expiry...")
            test_user.account_locked_until = None
            test_user.is_account_locked = False
            test_user.save()
        
        # Try login with correct password
        response = client.post(
            login_url,
            data=json.dumps({
                'email': email_address,
                'password': 'correctpassword123'
            }),
            content_type='application/json'
        )
        
        try:
            response_data = response.json()
        except:
            response_data = {'error': 'Invalid JSON response'}
        
        self.stdout.write(f"   📊 Status Code: {response.status_code}")
        
        if response.status_code == 200 and response_data.get('success'):
            self.stdout.write(f"   ✅ Login successful!")
            self.stdout.write(f"   🎉 User data: {response_data.get('user', {}).get('email', 'Unknown')}")
        else:
            self.stdout.write(f"   ❌ Login failed: {response_data}")
        
        # Final status
        test_user.refresh_from_db()
        self.stdout.write(f"\n📊 Final Status:")
        self.stdout.write(f"   🔢 Failed attempts: {test_user.failed_login_attempts}")
        self.stdout.write(f"   🔒 Account locked: {test_user.is_account_locked}")
        
        self.stdout.write(f"\n✅ Account Lockout Test Complete!")
        self.stdout.write(f"\n💡 Error Response Examples:")
        self.stdout.write(f"   🔒 Account Locked: HTTP 423 with ACCOUNT_LOCKED error code")
        self.stdout.write(f"   ❌ Invalid Credentials: HTTP 401 with INVALID_CREDENTIALS error code")
        self.stdout.write(f"   🚫 Account Deactivated: HTTP 403 with ACCOUNT_DEACTIVATED error code")
