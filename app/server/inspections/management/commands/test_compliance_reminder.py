"""
Management command to test compliance deadline reminder
This command helps set up test data and trigger reminders for testing purposes
Run this command:
    python manage.py test_compliance_reminder --hours 24
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from inspections.models import Inspection, NoticeOfViolation, InspectionForm
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Test compliance deadline reminder by setting up test data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='Number of hours from now to set the deadline (default: 24)',
        )
        parser.add_argument(
            '--inspection-id',
            type=int,
            help='Specific inspection ID to use (optional)',
        )
        parser.add_argument(
            '--email',
            type=str,
            help='Email address to send test reminder to',
            default=None,
        )

    def handle(self, *args, **options):
        hours = options.get('hours', 24)
        inspection_id = options.get('inspection_id')
        test_email = options.get('email')
        
        self.stdout.write(self.style.SUCCESS('🧪 Testing Compliance Deadline Reminder'))
        self.stdout.write('=' * 60)
        
        # Find an inspection with NOV_SENT status
        if inspection_id:
            try:
                inspection = Inspection.objects.get(id=inspection_id, current_status='NOV_SENT')
            except Inspection.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Inspection {inspection_id} not found or not in NOV_SENT status')
                )
                return
        else:
            # Find any inspection with NOV_SENT status that has a NOV
            inspection = Inspection.objects.filter(
                current_status='NOV_SENT'
            ).prefetch_related('form__nov', 'establishments').first()
            
            if not inspection:
                self.stdout.write(
                    self.style.ERROR('No inspections with NOV_SENT status found. Please send a NOV first.')
                )
                return
        
        # Get or create NOV
        if not hasattr(inspection, 'form') or not inspection.form:
            self.stdout.write(
                self.style.ERROR(f'Inspection {inspection.code} does not have a form')
            )
            return
        
        nov, created = NoticeOfViolation.objects.get_or_create(
            inspection_form=inspection.form,
            defaults={
                'sent_date': timezone.now().date(),
                'compliance_deadline': timezone.now() + timedelta(hours=hours),
                'violations': 'Test violations for reminder testing',
                'compliance_instructions': 'Test compliance instructions for reminder testing',
                'recipient_email': test_email or 'test@example.com',
                'recipient_name': 'Test Recipient',
                'contact_person': 'Test Contact Person',
            }
        )
        
        if not created:
            # Update existing NOV
            nov.compliance_deadline = timezone.now() + timedelta(hours=hours)
            if test_email:
                nov.recipient_email = test_email
            nov.save()
            self.stdout.write(
                self.style.SUCCESS(f'✓ Updated existing NOV for inspection {inspection.code}')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'✓ Created test NOV for inspection {inspection.code}')
            )
        
        establishment = inspection.establishments.first()
        establishment_name = establishment.name if establishment else 'N/A'
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Test Data Setup:'))
        self.stdout.write(f'  Inspection Code: {inspection.code}')
        self.stdout.write(f'  Establishment: {establishment_name}')
        self.stdout.write(f'  Recipient Email: {nov.recipient_email}')
        self.stdout.write(f'  Compliance Deadline: {nov.compliance_deadline.strftime("%B %d, %Y at %I:%M %p")}')
        self.stdout.write(f'  Hours from now: {hours}')
        self.stdout.write('')
        
        # Check if deadline is in the reminder window (23-25 hours)
        now = timezone.now()
        hours_until = (nov.compliance_deadline - now).total_seconds() / 3600
        
        if 23 <= hours_until <= 25:
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ Deadline is in reminder window ({hours_until:.1f} hours away)'
                )
            )
            self.stdout.write('')
            self.stdout.write('To test the reminder, run:')
            self.stdout.write(
                self.style.WARNING('  python manage.py send_nov_compliance_reminders')
            )
            self.stdout.write('')
            self.stdout.write('Or with dry-run (no email sent):')
            self.stdout.write(
                self.style.WARNING('  python manage.py send_nov_compliance_reminders --dry-run')
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f'⚠ Deadline is {hours_until:.1f} hours away (reminder window is 23-25 hours)'
                )
            )
            self.stdout.write('')
            self.stdout.write('The reminder command checks for deadlines between 23-25 hours from now.')
            self.stdout.write('You may need to adjust the --hours parameter or wait for the deadline to enter the window.')
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('✅ Test setup complete!'))

