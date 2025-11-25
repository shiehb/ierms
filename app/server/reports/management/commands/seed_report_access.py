"""
Management command to seed ReportAccess table with default role-to-report mappings
"""
from django.core.management.base import BaseCommand
from reports.models import ReportAccess


class Command(BaseCommand):
    help = 'Seed ReportAccess table with default role-to-report mappings'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear all existing entries before seeding (recommended)',
        )
    
    def handle(self, *args, **options):
        self.stdout.write('Seeding ReportAccess data...')
        
        # Clear existing data if --clear flag is set
        if options['clear']:
            deleted_count = ReportAccess.objects.count()
            ReportAccess.objects.all().delete()
            self.stdout.write(
                self.style.WARNING(f'🗑️  Deleted {deleted_count} existing entries')
            )
        else:
            self.stdout.write(
                self.style.WARNING('⚠️  Not clearing existing entries. Use --clear to remove old permissions.')
            )
        
        # Define default access mappings (matches seed_report_access.sql)
        DEFAULT_ACCESS = {
            "Monitoring Personnel": ["inspection", "monitoring_accomplishment"],
            "Unit Head": ["inspection", "compliance", "non_compliant", "unit_accomplishment", "quota"],
            "Section Chief": ["inspection", "compliance", "non_compliant", "section_accomplishment", "quota"],
            "Division Chief": ["establishment", "quota", "compliance", "non_compliant", "inspection"],
            "Legal Unit": ["billing", "non_compliant", "compliance", "nov", "noo"],
            "Admin": ["user", "establishment", "law", "quota", "billing", "compliance", "non_compliant", "inspection", "nov", "noo"],
        }
        
        # Display name mapping
        DISPLAY_NAMES = {
            "user": "User Report",
            "establishment": "Establishment Report",
            "law": "Law Report",
            "quota": "Quota Report",
            "billing": "Billing Report",
            "compliance": "Compliance Report",
            "non_compliant": "Non-Compliant Report",
            "inspection": "Inspection Report",
            "section_accomplishment": "Section Accomplishment Report",
            "unit_accomplishment": "Unit Accomplishment Report",
            "monitoring_accomplishment": "Monitoring Accomplishment Report",
            "nov": "Notice of Violation Report",
            "noo": "Notice of Order Report",
        }
        
        created_count = 0
        skipped_count = 0
        
        for role, report_types in DEFAULT_ACCESS.items():
            for report_type in report_types:
                # Check if this combination already exists
                exists = ReportAccess.objects.filter(
                    role=role,
                    report_type=report_type
                ).exists()
                
                if not exists:
                    ReportAccess.objects.create(
                        role=role,
                        report_type=report_type,
                        display_name=DISPLAY_NAMES.get(report_type, report_type.replace('_', ' ').title())
                    )
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Created: {role} -> {DISPLAY_NAMES.get(report_type, report_type)}')
                    )
                else:
                    skipped_count += 1
                    self.stdout.write(
                        self.style.WARNING(f'⊘ Skipped (already exists): {role} -> {DISPLAY_NAMES.get(report_type, report_type)}')
                    )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Completed! Created: {created_count}, Skipped: {skipped_count}'
            )
        )
        
        # Show summary by role
        self.stdout.write('\n📊 Final Summary by Role:')
        self.stdout.write('-' * 60)
        for role in sorted(DEFAULT_ACCESS.keys()):
            count = ReportAccess.objects.filter(role=role).count()
            reports = ReportAccess.objects.filter(role=role).values_list('display_name', flat=True)
            self.stdout.write(f'{role}: {count} reports')
            for report in reports:
                self.stdout.write(f'  • {report}')

