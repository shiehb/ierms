"""
Management command to check ReportAccess configuration and diagnose access issues
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from reports.models import ReportAccess

User = get_user_model()


class Command(BaseCommand):
    help = 'Check ReportAccess configuration and diagnose access issues'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            type=str,
            help='Email of user to check access for',
        )
        parser.add_argument(
            '--role',
            type=str,
            help='Role to check access for',
        )
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.HTTP_INFO('=' * 70))
        self.stdout.write(self.style.HTTP_INFO('  REPORT ACCESS DIAGNOSTIC TOOL'))
        self.stdout.write(self.style.HTTP_INFO('=' * 70))
        self.stdout.write('')
        
        # Check if ReportAccess table has data
        total_count = ReportAccess.objects.count()
        self.stdout.write(f'📊 Total ReportAccess entries: {total_count}')
        
        if total_count == 0:
            self.stdout.write(self.style.ERROR('❌ ReportAccess table is EMPTY!'))
            self.stdout.write(self.style.WARNING('   Run: python manage.py seed_report_access'))
            self.stdout.write(self.style.WARNING('   OR execute: server/seed_report_access.sql'))
            return
        
        self.stdout.write('')
        
        # Show roles in database
        roles = ReportAccess.objects.values_list('role', flat=True).distinct()
        self.stdout.write('📋 Roles configured in ReportAccess:')
        for role in roles:
            count = ReportAccess.objects.filter(role=role).count()
            self.stdout.write(f'   • {role}: {count} reports')
        
        self.stdout.write('')
        
        # Check specific user if provided
        if options['user']:
            email = options['user']
            try:
                user = User.objects.get(email=email)
                self.stdout.write(self.style.HTTP_INFO('👤 User Information:'))
                self.stdout.write(f'   Email: {user.email}')
                self.stdout.write(f'   Name: {user.first_name} {user.last_name}')
                self.stdout.write(f'   Role (userlevel): "{user.userlevel}"')
                self.stdout.write(f'   Section: {user.section or "None"}')
                self.stdout.write(f'   Is Active: {user.is_active}')
                self.stdout.write('')
                
                # Check access for this user
                user_reports = ReportAccess.objects.filter(role=user.userlevel)
                
                if user_reports.exists():
                    self.stdout.write(self.style.SUCCESS(f'✅ {user_reports.count()} reports accessible:'))
                    for report in user_reports:
                        self.stdout.write(f'   ✓ {report.display_name} ({report.report_type})')
                else:
                    self.stdout.write(self.style.ERROR(f'❌ No reports found for role: "{user.userlevel}"'))
                    self.stdout.write(self.style.WARNING('   Possible issues:'))
                    self.stdout.write(f'   • Role spelling mismatch (check case sensitivity)')
                    self.stdout.write(f'   • Role not in ReportAccess table')
                    self.stdout.write(f'   • Expected one of: {", ".join(roles)}')
                
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'❌ User not found: {email}'))
            
            self.stdout.write('')
        
        # Check specific role if provided
        if options['role']:
            role = options['role']
            self.stdout.write(self.style.HTTP_INFO(f'🔍 Checking role: "{role}"'))
            
            role_reports = ReportAccess.objects.filter(role=role)
            
            if role_reports.exists():
                self.stdout.write(self.style.SUCCESS(f'✅ {role_reports.count()} reports configured:'))
                for report in role_reports:
                    self.stdout.write(f'   ✓ {report.display_name} ({report.report_type})')
            else:
                self.stdout.write(self.style.ERROR(f'❌ No reports found for role: "{role}"'))
                
                # Check for similar roles (case-insensitive)
                similar_roles = ReportAccess.objects.filter(
                    role__iexact=role
                ).values_list('role', flat=True).distinct()
                
                if similar_roles:
                    self.stdout.write(self.style.WARNING(f'   Did you mean: {", ".join(similar_roles)}?'))
                else:
                    self.stdout.write(self.style.WARNING('   Available roles:'))
                    for r in roles:
                        self.stdout.write(f'     • {r}')
            
            self.stdout.write('')
        
        # Show summary by role
        if not options['user'] and not options['role']:
            self.stdout.write('📈 Summary by Role:')
            self.stdout.write('')
            for role in sorted(roles):
                reports = ReportAccess.objects.filter(role=role).order_by('display_name')
                self.stdout.write(self.style.SUCCESS(f'  {role} ({reports.count()} reports):'))
                for report in reports:
                    self.stdout.write(f'    • {report.display_name}')
                self.stdout.write('')
        
        # Show users and their roles
        self.stdout.write('👥 Active Users and Their Roles:')
        users = User.objects.filter(is_active=True).order_by('userlevel', 'email')
        
        current_role = None
        for user in users:
            if current_role != user.userlevel:
                current_role = user.userlevel
                report_count = ReportAccess.objects.filter(role=current_role).count()
                if report_count > 0:
                    status_icon = '✅'
                    status_color = self.style.SUCCESS
                else:
                    status_icon = '❌'
                    status_color = self.style.ERROR
                self.stdout.write('')
                self.stdout.write(status_color(f'{status_icon} {current_role} ({report_count} reports):'))
            
            self.stdout.write(f'   • {user.email}')
        
        self.stdout.write('')
        self.stdout.write(self.style.HTTP_INFO('=' * 70))
        self.stdout.write('💡 Tips:')
        self.stdout.write('   • Run with --user=email@example.com to check specific user')
        self.stdout.write('   • Run with --role="Section Chief" to check specific role')
        self.stdout.write('   • Roles are case-sensitive!')
        self.stdout.write('   • If table is empty, run: python manage.py seed_report_access')
        self.stdout.write(self.style.HTTP_INFO('=' * 70))

