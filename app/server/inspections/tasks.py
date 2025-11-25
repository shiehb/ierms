"""
Celery tasks for inspections app
"""
from celery import shared_task
from django.core.management import call_command
import logging

logger = logging.getLogger(__name__)


@shared_task
def send_nov_compliance_reminders():
    """
    Send compliance reminders to establishment owners 1 day before NOV deadline.
    This task runs daily via Celery Beat.
    """
    try:
        logger.info("Starting NOV compliance reminder task")
        call_command('send_nov_compliance_reminders')
        logger.info("NOV compliance reminder task completed successfully")
        return "NOV compliance reminders sent successfully"
    except Exception as e:
        logger.error(f"Error in NOV compliance reminder task: {str(e)}")
        raise

