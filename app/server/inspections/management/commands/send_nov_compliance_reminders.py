"""
Management command to send compliance reminders 1 day before NOV deadline
Run this command daily via cron or Celery Beat:
    python manage.py send_nov_compliance_reminders
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
from inspections.models import Inspection, NoticeOfViolation
from inspections.utils import send_notice_email
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Send compliance reminders to establishment owners 1 day before NOV deadline'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without sending emails (test mode)',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('Running in DRY RUN mode - no emails will be sent'))
        
        now = timezone.now()
        # Check for deadlines that are approximately 1 day away (within 24 hours)
        # We check for deadlines between now + 23 hours and now + 25 hours to account for timing
        reminder_count = 0
        
        # Find all NOV records with compliance deadlines approximately 1 day from now
        # We'll check for deadlines between 23-25 hours from now to catch them even if run at different times
        tomorrow_start = now + timedelta(hours=23)
        tomorrow_end = now + timedelta(hours=25)
        
        # Filter NOVs by deadline range and inspection status at database level
        novs = NoticeOfViolation.objects.filter(
            compliance_deadline__gte=tomorrow_start,
            compliance_deadline__lte=tomorrow_end,
            inspection_form__inspection__current_status='NOV_SENT',
            recipient_email__isnull=False
        ).exclude(
            recipient_email=''
        ).select_related(
            'inspection_form__inspection'
        ).prefetch_related(
            'inspection_form__inspection__establishments'
        )
        
        for nov in novs:
            inspection = nov.inspection_form.inspection
            
            establishment = inspection.establishments.first()
            establishment_name = establishment.name if establishment else 'N/A'
            
            # Calculate hours until deadline for logging
            hours_until_deadline = (nov.compliance_deadline - now).total_seconds() / 3600
            
            # Generate reminder email (plain text fallback)
            subject = f"Reminder: Compliance Deadline Tomorrow - {inspection.code}"
            body = self._generate_reminder_email_body(
                inspection, 
                establishment_name, 
                nov
            )
            
            self.stdout.write(
                self.style.WARNING(
                    f'Reminder needed: {inspection.code} - {establishment_name} '
                    f'(deadline: {nov.compliance_deadline.strftime("%B %d, %Y at %I:%M %p")}, '
                    f'{hours_until_deadline:.1f} hours remaining)'
                )
            )
            
            if not dry_run:
                try:
                    # Get inspection date from form if available
                    inspection_date = 'N/A'
                    if hasattr(inspection, 'form') and inspection.form:
                        try:
                            if hasattr(inspection.form, 'checklist') and inspection.form.checklist:
                                if isinstance(inspection.form.checklist, dict):
                                    general = inspection.form.checklist.get('general', {})
                                    if general and general.get('inspection_date_time'):
                                        from django.utils.dateparse import parse_datetime
                                        date_obj = parse_datetime(general.get('inspection_date_time'))
                                        if date_obj:
                                            inspection_date = date_obj.strftime('%B %d, %Y')
                        except Exception:
                            pass
                    
                    # Format deadline date and time
                    deadline_date = nov.compliance_deadline.strftime('%B %d, %Y') if nov.compliance_deadline else 'N/A'
                    deadline_time = nov.compliance_deadline.strftime('%I:%M %p') if nov.compliance_deadline else None
                    
                    # Get NOV sent date
                    nov_sent_date = nov.sent_date.strftime('%B %d, %Y') if nov.sent_date else None
                    
                    # Prepare template context for professional HTML email
                    email_context = {
                        'inspection_code': inspection.code,
                        'inspection_date': inspection_date,
                        'establishment_name': establishment_name,
                        'recipient_name': nov.recipient_name or nov.contact_person or 'Sir/Madam',
                        'contact_person': nov.contact_person or '',
                        'violations': nov.violations or '',
                        'compliance_instructions': nov.compliance_instructions or '',
                        'compliance_deadline': nov.compliance_deadline,
                        'deadline_date': deadline_date,
                        'deadline_time': deadline_time,
                        'nov_sent_date': nov_sent_date,
                        'is_reminder': True,
                    }
                    
                    # Send email using professional HTML template
                    send_notice_email(
                        subject, 
                        body,  # Plain text fallback
                        nov.recipient_email,
                        notice_type='NOV_REMINDER',
                        context=email_context
                    )
                    reminder_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  ✓ Reminder sent to {nov.recipient_email}'
                        )
                    )
                    logger.info(f"NOV compliance reminder sent for {inspection.code} to {nov.recipient_email}")
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'  ✗ Failed to send reminder to {nov.recipient_email}: {str(e)}'
                        )
                    )
                    logger.error(f"Failed to send NOV compliance reminder for {inspection.code}: {str(e)}", exc_info=True)
            else:
                reminder_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  [DRY RUN] Would send reminder to {nov.recipient_email}'
                    )
                )
        
        if reminder_count == 0:
            self.stdout.write(self.style.SUCCESS('No reminders needed at this time'))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Processed {reminder_count} compliance reminder(s)'
                )
            )
    
    def _generate_reminder_email_body(self, inspection, establishment_name, nov):
        """Generate email body for compliance deadline reminder"""
        deadline_str = nov.compliance_deadline.strftime("%B %d, %Y at %I:%M %p")
        deadline_date = nov.compliance_deadline.strftime("%B %d, %Y")
        
        recipient_name = nov.recipient_name or nov.contact_person or 'Sir/Madam'
        
        body = f"""
Dear {recipient_name},

This is a reminder that your compliance deadline for the Notice of Violation (NOV) is approaching.

IMPORTANT: Your compliance deadline is TOMORROW ({deadline_date}).

Inspection Details:
- Inspection Code: {inspection.code}
- Establishment: {establishment_name}
- Compliance Deadline: {deadline_str}
- Law: {inspection.law}

Violations Found:
{nov.violations or 'No violations listed'}

Compliance Instructions:
{nov.compliance_instructions or 'No instructions listed'}

Required Actions:
Please ensure all required compliance actions are completed and submitted before the deadline to avoid further penalties or legal action.

If you have already completed the compliance requirements, please submit your compliance documents as soon as possible.

If you have any questions or need clarification regarding the compliance requirements, please contact the Legal Unit immediately.

Thank you for your prompt attention to this matter.

Best regards,
Legal Unit
Integrated Establishments Regulatory Management System

---
This is an automated reminder from the Integrated Establishments Regulatory Management System.
Original NOV was sent on {nov.sent_date.strftime("%B %d, %Y") if nov.sent_date else 'N/A'}.
"""
        return body

