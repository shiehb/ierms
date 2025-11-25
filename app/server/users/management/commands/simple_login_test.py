from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.test import Client
import json

User = get_user_model()

class Command(BaseCommand):
    help = 'Simple login test'

    def handle(self, *args, **options):
        self.stdout.write("🔐 Simple Login Test")
        self.stdout.write("=" * 30)
        
        # Create test user
        user, created = User.objects.get_or_create(
            email='test@example.com',
            defaults={
                'first_name': 'Test',
                'last_name': 'User',
                'userlevel': 'Inspector'
            }
        )
        
        if created:
            user.set_password('password123')
            user.save()
            self.stdout.write("✅ Created test user: test@example.com")
            self.stdout.write("   Password: password123")
        
        client = Client()
        
        # Test successful login
        self.stdout.write("\n✅ Testing successful login...")
        response = client.post('/api/auth/login/', {
            'email': 'test@example.com',
            'password': 'password123'
        }, content_type='application/json')
        
        if response.status_code == 200:
            self.stdout.write("   ✅ Login successful")
        else:
            self.stdout.write(f"   ❌ Login failed: {response.status_code}")
        
        # Test wrong password
        self.stdout.write("\n❌ Testing wrong password...")
        response = client.post('/api/auth/login/', {
            'email': 'test@example.com',
            'password': 'wrongpassword'
        }, content_type='application/json')
        
        data = response.json()
        self.stdout.write(f"   Status: {response.status_code}")
        self.stdout.write(f"   Error: {data.get('error', 'None')}")
        
        self.stdout.write("\n✅ Simple test complete!")
