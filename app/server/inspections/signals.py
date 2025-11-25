from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from .models import Inspection, InspectionHistory, ReinspectionSchedule
from audit.utils import log_activity
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


@receiver(post_save, sender=Inspection)
def log_inspection_creation(sender, instance, created, **kwargs):
    """Log inspection creation"""
    if created and instance.created_by:
        try:
            # Get establishment names for logging
            establishment_names = [est.name for est in instance.establishments.all()]
            establishment_list = ", ".join(establishment_names) if establishment_names else "No establishments"
            
            log_activity(
                instance.created_by,
                "create",
                f"Inspection {instance.code} created for establishments: {establishment_list} with law {instance.law}",
                request=None
            )
            
            logger.info(f"Inspection {instance.code} created by {instance.created_by.email}")
            
        except Exception as e:
            logger.error(f"Failed to log inspection creation: {str(e)}")


@receiver(post_save, sender=Inspection)
def create_reinspection_schedule(sender, instance, created, **kwargs):
    """Create reinspection schedule when inspection is closed"""
    if not created and instance.current_status in ['CLOSED_COMPLIANT', 'CLOSED_NON_COMPLIANT']:
        try:
            # Determine compliance status and reinspection period
            if instance.current_status == 'CLOSED_COMPLIANT':
                compliance_status = 'COMPLIANT'
                # 2-3 years for compliant (using 2.5 years as default)
                reinspection_period = timedelta(days=912)  # ~2.5 years
            else:  # CLOSED_NON_COMPLIANT
                compliance_status = 'NON_COMPLIANT'
                # 1 year for non-compliant
                reinspection_period = timedelta(days=365)
            
            # Create reinspection schedule for each establishment
            for establishment in instance.establishments.all():
                due_date = timezone.now().date() + reinspection_period
                
                # Create or update reinspection schedule
                schedule, created = ReinspectionSchedule.objects.get_or_create(
                    establishment=establishment,
                    original_inspection=instance,
                    defaults={
                        'compliance_status': compliance_status,
                        'due_date': due_date,
                        'status': 'PENDING'
                    }
                )
                
                if not created:
                    # Update existing schedule if inspection was reopened and closed again
                    schedule.compliance_status = compliance_status
                    schedule.due_date = due_date
                    schedule.status = 'PENDING'
                    schedule.reminder_sent = False
                    schedule.reminder_sent_date = None
                    schedule.save()
                
                logger.info(f"Reinspection schedule created for {establishment.name} due {due_date}")
                
        except Exception as e:
            logger.error(f"Failed to create reinspection schedule for {instance.code}: {str(e)}")


@receiver(post_save, sender=InspectionHistory)
def log_inspection_status_change(sender, instance, created, **kwargs):
    """Log inspection status changes"""
    if created and instance.changed_by:
        try:
            log_activity(
                instance.changed_by,
                "status_change",
                f"Inspection {instance.inspection.code} status changed from {instance.previous_status} to {instance.new_status}",
                request=None
            )
            
            logger.info(f"Inspection {instance.inspection.code} status changed by {instance.changed_by.email}")
            
        except Exception as e:
            logger.error(f"Failed to log inspection status change: {str(e)}")

