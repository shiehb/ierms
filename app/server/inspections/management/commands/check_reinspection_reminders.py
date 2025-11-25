"""
Management command to check for upcoming reinspection deadlines and notify Division Chiefs
Run this command daily via cron or task scheduler:
    python manage.py check_reinspection_reminders
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from datetime import timedelta
from inspections.models import ReinspectionSchedule
from notifications.models import Notification
from users.models import User
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Check for upcoming reinspection deadlines and notify Division Chiefs'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without sending notifications (test mode)',
        )
        parser.add_argument(
            '--days-ahead',
            type=int,
            default=30,
            help='Number of days ahead to check for upcoming reinspections (default: 30)',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        days_ahead = options.get('days_ahead', 30)
        
        self.stdout.write(f"Checking reinspection reminders {days_ahead} days ahead...")
        
        # Calculate date range
        today = timezone.now().date()
        check_date = today + timedelta(days=days_ahead)
        
        # Find upcoming reinspections
        upcoming_schedules = ReinspectionSchedule.objects.filter(
            due_date__lte=check_date,
            due_date__gte=today,
            status='PENDING',
            reminder_sent=False
        ).select_related('establishment', 'original_inspection')
        
        self.stdout.write(f"Found {upcoming_schedules.count()} upcoming reinspections")
        
        # Get Division Chiefs
        division_chiefs = User.objects.filter(
            userlevel='Division Chief',
            is_active=True
        )
        
        if not division_chiefs.exists():
            self.stdout.write(self.style.WARNING("No active Division Chiefs found"))
            return
        
        notifications_sent = 0
        
        for schedule in upcoming_schedules:
            try:
                # Calculate days until due
                days_until_due = (schedule.due_date - today).days
                
                # Create notification for each Division Chief
                for chief in division_chiefs:
                    # Create in-app notification
                    notification = Notification.objects.create(
                        recipient=chief,
                        notification_type='reinspection_reminder',
                        title=f'Reinspection Reminder - {schedule.establishment.name}',
                        message=self._create_reminder_message(schedule, days_until_due),
                        related_object_type='reinspection_schedule',
                        related_object_id=schedule.id
                    )
                    
                    # Send email notification
                    if not dry_run:
                        self._send_email_reminder(chief, schedule, days_until_due)
                    
                    notifications_sent += 1
                    self.stdout.write(f"Reminder sent to {chief.email} for {schedule.establishment.name}")
                
                # Mark reminder as sent
                if not dry_run:
                    schedule.reminder_sent = True
                    schedule.reminder_sent_date = timezone.now()
                    schedule.save()
                
            except Exception as e:
                logger.error(f"Failed to send reminder for {schedule.establishment.name}: {str(e)}")
                self.stdout.write(
                    self.style.ERROR(f"Failed to send reminder for {schedule.establishment.name}: {str(e)}")
                )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"DRY RUN: Would have sent {notifications_sent} notifications")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Successfully sent {notifications_sent} reinspection reminders")
            )

    def _create_reminder_message(self, schedule, days_until_due):
        """Create reminder message for notification"""
        compliance_text = "Compliant" if schedule.compliance_status == 'COMPLIANT' else "Non-Compliant"
        
        if days_until_due == 0:
            urgency = "TODAY"
        elif days_until_due <= 7:
            urgency = "URGENT"
        elif days_until_due <= 30:
            urgency = "SOON"
        else:
            urgency = "UPCOMING"
        
        message = f"""
{urgency}: Reinspection due for {schedule.establishment.name}

Establishment: {schedule.establishment.name}
Original Inspection: {schedule.original_inspection.code}
Compliance Status: {compliance_text}
Due Date: {schedule.due_date}
Days Until Due: {days_until_due}

Please schedule the reinspection accordingly.
        """.strip()
        
        return message

    def _send_email_reminder(self, chief, schedule, days_until_due):
        """Send email reminder to Division Chief"""
        try:
            compliance_text = "Compliant" if schedule.compliance_status == 'COMPLIANT' else "Non-Compliant"
            
            subject = f"Reinspection Reminder - {schedule.establishment.name}"
            
            # Construct address manually
            establishment = schedule.establishment
            address_parts = [
                establishment.street_building,
                establishment.barangay,
                establishment.city,
                establishment.province
            ]
            full_address = ', '.join(filter(None, address_parts))
            
            message = f"""
Dear {chief.first_name or chief.email},

This is a reminder that a reinspection is due for the following establishment:

Establishment: {schedule.establishment.name}
Address: {full_address}
Original Inspection Code: {schedule.original_inspection.code}
Compliance Status: {compliance_text}
Due Date: {schedule.due_date}
Days Until Due: {days_until_due}

Please schedule the reinspection accordingly.

Best regards,
Environmental Management System
            """.strip()
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[chief.email],
                fail_silently=False,
            )
            
            logger.info(f"Email reminder sent to {chief.email} for {schedule.establishment.name}")
            
        except Exception as e:
            logger.error(f"Failed to send email reminder to {chief.email}: {str(e)}")
            raise
