"""
Management command to check for expired compliance deadlines and notify Legal Unit
Run this command daily via cron or task scheduler:
    python manage.py check_compliance_deadlines
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from inspections.models import Inspection, InspectionForm
from notifications.models import Notification
from users.models import User


class Command(BaseCommand):
    help = 'Check for expired compliance deadlines and notify Legal Unit'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without sending notifications (test mode)',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('Running in DRY RUN mode - no notifications will be sent'))
        
        now = timezone.now()
        expired_count = 0
        
        # Find all inspections with expired compliance deadlines
        inspections = Inspection.objects.filter(
            current_status__in=['NOV_SENT', 'NOO_SENT']
        ).select_related('form').prefetch_related('establishments')
        
        # Get all Legal Unit users for notifications
        legal_users = User.objects.filter(userlevel='Legal Unit', is_active=True)
        
        if not legal_users.exists():
            self.stdout.write(self.style.ERROR('No active Legal Unit users found!'))
            return
        
        for inspection in inspections:
            form = getattr(inspection, 'form', None)
            
            if not form or not form.nov_compliance_date:
                continue
            
            # Check if deadline has passed
            if form.nov_compliance_date >= now:
                continue
            
            # Check if we've already notified today
            today = now.date()
            recent_notification = Notification.objects.filter(
                notification_type='COMPLIANCE_EXPIRED',
                related_object_id=inspection.id,
                created_at__date=today
            ).exists()
            
            if recent_notification:
                self.stdout.write(f'Already notified for {inspection.code} today - skipping')
                continue
            
            expired_count += 1
            days_overdue = (now.date() - form.nov_compliance_date.date()).days
            
            establishment = inspection.establishments.first()
            establishment_name = establishment.name if establishment else 'N/A'
            
            self.stdout.write(
                self.style.WARNING(
                    f'Expired: {inspection.code} - {establishment_name} '
                    f'({days_overdue} days overdue)'
                )
            )
            
            if not dry_run:
                # Send notifications to all Legal Unit users
                for legal_user in legal_users:
                    # Create in-app notification
                    notification = Notification.objects.create(
                        user=legal_user,
                        notification_type='COMPLIANCE_EXPIRED',
                        title=f'Compliance Deadline Expired - {inspection.code}',
                        message=(
                            f'The compliance deadline for inspection {inspection.code} '
                            f'({establishment_name}) has expired. '
                            f'Deadline was {form.nov_compliance_date.strftime("%B %d, %Y at %I:%M %p")}. '
                            f'Currently {days_overdue} days overdue.'
                        ),
                        related_object_type='inspection',
                        related_object_id=inspection.id
                    )
                    
                    # Send email notification
                    if legal_user.email:
                        try:
                            send_mail(
                                subject=f'Compliance Deadline Expired - {inspection.code}',
                                message=self._generate_email_body(
                                    inspection, 
                                    establishment_name, 
                                    form, 
                                    days_overdue
                                ),
                                from_email=settings.DEFAULT_FROM_EMAIL,
                                recipient_list=[legal_user.email],
                                fail_silently=False,
                            )
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'  ✓ Email sent to {legal_user.email}'
                                )
                            )
                        except Exception as e:
                            self.stdout.write(
                                self.style.ERROR(
                                    f'  ✗ Failed to send email to {legal_user.email}: {str(e)}'
                                )
                            )
        
        if expired_count == 0:
            self.stdout.write(self.style.SUCCESS('No expired compliance deadlines found'))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Processed {expired_count} expired compliance deadline(s)'
                )
            )
    
    def _generate_email_body(self, inspection, establishment_name, form, days_overdue):
        """Generate email body for compliance deadline expiration"""
        return f"""
Compliance Deadline Expired

Inspection Details:
- Inspection Code: {inspection.code}
- Establishment: {establishment_name}
- Current Status: {inspection.get_current_status_display()}
- Original Deadline: {form.nov_compliance_date.strftime("%B %d, %Y at %I:%M %p")}
- Days Overdue: {days_overdue}

Violations:
{form.nov_violations or form.violations_found or 'No violations listed'}

Compliance Instructions:
{form.nov_compliance_instructions or 'No instructions listed'}

Suggested Actions:
1. Review inspection status
2. Send Notice of Order (NOO) with penalties if not already sent
3. Escalate to higher authority if necessary
4. Mark as non-compliant and close if appropriate

View this inspection at:
{settings.FRONTEND_URL or 'http://localhost:5173'}/inspections/{inspection.id}/review

---
This is an automated notification from the Integrated Establishments Regulatory Management System.
"""

