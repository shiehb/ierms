"""
Utility functions for inspections app
"""
import logging
from django.core.mail import send_mail, EmailMessage, EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags, linebreaks

logger = logging.getLogger(__name__)


def send_notice_email(subject, body, recipient_email, notice_type='NOV', context=None):
    """
    Send NOV/NOO notices to establishments using professional government-style templates.
    
    Args:
        subject: Email subject line
        body: Plain text body (used as fallback)
        recipient_email: Recipient email address
        notice_type: 'NOV' or 'NOO'
        context: Dictionary with template context variables
    """
    try:
        # Validate recipient email
        if not recipient_email or not recipient_email.strip():
            raise ValueError("Recipient email is required and cannot be empty")
        
        recipient_email = recipient_email.strip()
        
        # Check email backend configuration
        from django.core.mail import get_connection
        connection = get_connection()
        backend_name = connection.__class__.__name__
        
        if 'console' in backend_name.lower():
            logger.warning(f"Email backend is set to console - email will not actually be sent to {recipient_email}")
            logger.warning("Please configure EMAIL_HOST_USER and EMAIL_HOST_PASSWORD in settings or environment variables")
        
        # Prepare context for template
        template_context = context or {}
        
        # Add default values if not provided
        from django.utils import timezone
        from django.contrib.humanize.templatetags.humanize import intcomma
        from decimal import Decimal
        
        template_context.setdefault('site_url', getattr(settings, 'FRONTEND_URL', 'http://localhost:3000'))
        template_context.setdefault('current_year', timezone.now().year)
        
        # Format penalty fees with comma separators if it's a number
        if 'penalty_fees' in template_context:
            try:
                penalty = template_context['penalty_fees']
                if isinstance(penalty, (int, float, Decimal)):
                    template_context['penalty_fees'] = f"{float(penalty):,.2f}"
            except Exception:
                pass
        
        # Select template based on notice type
        if notice_type.upper() == 'NOO':
            template_name = 'emails/notice_of_order.html'
        elif notice_type.upper() == 'NOV_REMINDER':
            template_name = 'emails/nov_compliance_reminder.html'
        else:
            template_name = 'emails/notice_of_violation.html'
        
        # Render HTML template
        try:
            html_body = render_to_string(template_name, template_context)
        except Exception as template_error:
            logger.warning(f"Failed to render email template, using plain text fallback: {str(template_error)}")
            # Fallback to plain text with linebreaks
            html_body = linebreaks(body)
        
        # Create plain text version from HTML
        plain_text = strip_tags(html_body)
        # Clean up plain text formatting
        import re
        plain_text = re.sub(r'\n\s*\n', '\n\n', plain_text)
        plain_text = plain_text.strip()
        
        # Create email
        email = EmailMultiAlternatives(
            subject=subject,
            body=plain_text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient_email],
        )
        email.attach_alternative(html_body, "text/html")
        
        logger.info(f"Sending {notice_type} email to {recipient_email} with subject '{subject}' using backend {backend_name}")
        email.send(fail_silently=False)
        logger.info(f"Notice email sent successfully to {recipient_email} with subject '{subject}'")
        return True
    except Exception as exc:
        logger.error(f"Failed to send notice email to {recipient_email}: {str(exc)}", exc_info=True)
        raise


def send_inspection_assignment_notification(user, inspection):
    """
    Send email notification when inspection is assigned to a user
    """
    try:
        # Get establishment names
        establishment_names = [est.name for est in inspection.establishments.all()]
        establishment_list = ", ".join(establishment_names) if establishment_names else "No establishments"
        
        subject = f"New Inspection Assignment: {inspection.code} - {establishment_list}"
        
        # Prepare email context
        context = {
            'user': user,
            'inspection': inspection,
            'establishment_list': establishment_list,
            'law': inspection.law,
            'site_url': getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
        }
        
        # Render email content
        html_message = render_to_string('emails/inspection_assignment_notification.html', context)
        plain_message = strip_tags(html_message)
        
        # Send email
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False
        )
        
        logger.info(f"Inspection assignment notification sent to {user.email}")
        
    except Exception as e:
        logger.error(f"Failed to send inspection assignment notification to {user.email}: {str(e)}")
        raise


def send_inspection_status_change_notification(user, inspection, old_status, new_status):
    """
    Send email notification when inspection status changes
    """
    try:
        # Get establishment names
        establishment_names = [est.name for est in inspection.establishments.all()]
        establishment_list = ", ".join(establishment_names) if establishment_names else "No establishments"
        
        subject = f"Inspection Status Update: {inspection.code} - {new_status}"
        
        # Prepare email context
        context = {
            'user': user,
            'inspection': inspection,
            'establishment_list': establishment_list,
            'old_status': old_status,
            'new_status': new_status,
            'law': inspection.law,
            'site_url': getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
        }
        
        # Render email content
        html_message = render_to_string('emails/inspection_status_change_notification.html', context)
        plain_message = strip_tags(html_message)
        
        # Send email
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False
        )
        
        logger.info(f"Inspection status change notification sent to {user.email}")
        
    except Exception as e:
        logger.error(f"Failed to send inspection status change notification to {user.email}: {str(e)}")
        raise


def send_inspection_forward_notification(user, inspection, forwarded_by, remarks=None):
    """
    Send email notification when inspection is forwarded to a user
    """
    try:
        # Get establishment names
        establishment_names = [est.name for est in inspection.establishments.all()]
        establishment_list = ", ".join(establishment_names) if establishment_names else "No establishments"
        
        subject = f"📋 URGENT: Inspection Forwarded: {inspection.code} - {establishment_list}"
        
        # Prepare email context
        context = {
            'user': user,
            'inspection': inspection,
            'establishment_list': establishment_list,
            'law': inspection.law,
            'forwarded_by': forwarded_by,
            'remarks': remarks,
            'site_url': getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
        }
        
        # Render email content
        html_message = render_to_string('emails/inspection_forward_notification.html', context)
        plain_message = strip_tags(html_message)
        
        # Send email
        email = EmailMessage(
            subject=subject,
            body=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        email.content_subtype = 'html'  # Set content type to HTML
        email.extra_headers = {
            'X-Priority': '1',
            'X-MSMail-Priority': 'High',
            'Importance': 'High',
            'X-Mailer': 'IERMS System - Urgent Notification'
        }
        email.send(fail_silently=False)
        
        logger.info(f"Inspection forward notification sent to {user.email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send inspection forward notification to {user.email}: {str(e)}")
        return False


def send_inspection_completion_notification(inspection, completed_by, next_assignee, completion_status):
    """
    Send email notification when inspection is completed and needs review (non-compliant only)
    """
    try:
        # Get establishment names
        establishment_names = [est.name for est in inspection.establishments.all()]
        establishment_list = ", ".join(establishment_names) if establishment_names else "No establishments"
        
        # Determine notification details based on completion status
        status_info = {
            'MONITORING_COMPLETED_COMPLIANT': {
                'subject_prefix': 'Monitoring Inspection Completed (Compliant)',
                'action_required': 'Unit Head Review Required',
                'next_reviewer': 'Unit Head'
            },
            'MONITORING_COMPLETED_NON_COMPLIANT': {
                'subject_prefix': 'Monitoring Inspection Completed (Non-Compliant)',
                'action_required': 'Unit Head Review Required',
                'next_reviewer': 'Unit Head'
            },
            'UNIT_COMPLETED_COMPLIANT': {
                'subject_prefix': 'Unit Inspection Completed (Compliant)',
                'action_required': 'Section Chief Review Required',
                'next_reviewer': 'Section Chief'
            },
            'UNIT_COMPLETED_NON_COMPLIANT': {
                'subject_prefix': 'Unit Inspection Completed (Non-Compliant)',
                'action_required': 'Section Chief Review Required',
                'next_reviewer': 'Section Chief'
            },
            'SECTION_COMPLETED_COMPLIANT': {
                'subject_prefix': 'Section Inspection Completed (Compliant)',
                'action_required': 'Division Chief Review Required',
                'next_reviewer': 'Division Chief'
            },
            'SECTION_COMPLETED_NON_COMPLIANT': {
                'subject_prefix': 'Section Inspection Completed (Non-Compliant)',
                'action_required': 'Division Chief Review Required',
                'next_reviewer': 'Division Chief'
            }
        }
        
        info = status_info.get(completion_status, {})
        subject = f"🚨 URGENT: {info.get('subject_prefix', 'Inspection Completed')}: {inspection.code} - {establishment_list}"
        
        # Get violations from form if available
        violations_found = ""
        try:
            if hasattr(inspection, 'form') and inspection.form:
                violations_found = inspection.form.violations_found or ""
        except:
            pass
        
        # Prepare email context
        context = {
            'inspection': inspection,
            'establishment_list': establishment_list,
            'completed_by': completed_by,
            'next_assignee': next_assignee,
            'completion_status': completion_status,
            'action_required': info.get('action_required', 'Review Required'),
            'next_reviewer': info.get('next_reviewer', 'Next Reviewer'),
            'law': inspection.law,
            'site_url': getattr(settings, 'FRONTEND_URL', 'http://localhost:3000'),
            'compliance_status': 'Compliant' if 'COMPLIANT' in completion_status else 'Non-Compliant',
            'violations_found': violations_found
        }
        
        # Render email content
        html_message = render_to_string('emails/inspection_completion_notification.html', context)
        plain_message = strip_tags(html_message)
        
        # Send email to next reviewer
        email = EmailMessage(
            subject=subject,
            body=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[next_assignee.email],
        )
        email.content_subtype = 'html'  # Set content type to HTML
        email.extra_headers = {
            'X-Priority': '1',
            'X-MSMail-Priority': 'High',
            'Importance': 'High',
            'X-Mailer': 'IERMS System - Urgent Notification'
        }
        email.send(fail_silently=False)
        
        logger.info(f"Inspection completion notification sent to {next_assignee.email} for {inspection.code}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send inspection completion notification for {inspection.code}: {str(e)}")
        return False


def create_completion_notification(recipient, inspection, completed_by, completion_status, remarks=None):
    """
    Create in-app notification when inspection is completed (both compliant and non-compliant)
    """
    try:
        from notifications.models import Notification
        
        # Get establishment names
        establishment_names = [est.name for est in inspection.establishments.all()]
        establishment_list = ", ".join(establishment_names) if establishment_names else "No establishments"
        
        # Determine notification details
        is_non_compliant = 'NON_COMPLIANT' in completion_status
        compliance_text = "Non-Compliant" if is_non_compliant else "Compliant"
        
        # Create notification message
        completed_by_name = f"{completed_by.first_name} {completed_by.last_name}" if completed_by.first_name else completed_by.email
        message = f"Inspection {inspection.code} for {establishment_list} has been completed as {compliance_text} by {completed_by_name}."
        
        if remarks:
            message += f" Remarks: {remarks}"
        
        # Create notification
        notification = Notification.objects.create(
            recipient=recipient,
            sender=completed_by,
            notification_type='inspection_completed',
            title=f'Inspection Completed ({compliance_text})',
            message=message,
            related_object_type='inspection',
            related_object_id=inspection.id if hasattr(inspection, 'id') else None
        )
        
        logger.info(f"In-app completion notification created for {recipient.email}")
        return notification
        
    except Exception as e:
        logger.error(f"Failed to create in-app completion notification for {recipient.email}: {str(e)}")
        return None


def send_inspection_review_notification(inspection, reviewer, next_assignee, review_status, is_compliant):
    """
    Send email notification when inspection review is completed and forwarded (non-compliant only)
    """
    try:
        # Only send email for non-compliant inspections
        if is_compliant:
            logger.info(f"Skipping email notification for compliant inspection {inspection.code}")
            return True
            
        establishment_names = [est.name for est in inspection.establishments.all()]
        establishment_list = ", ".join(establishment_names) if establishment_names else "No establishments"
        
        subject = f"⚠️ URGENT: Inspection Review Required (Non-Compliant): {inspection.code} - {establishment_list}"
        
        # Determine next action based on review status
        next_action_map = {
            'UNIT_REVIEWED': 'Section Chief Review Required',
            'SECTION_REVIEWED': 'Division Chief Review Required',
            'DIVISION_REVIEWED': 'Legal Action Required'
        }
        next_action = next_action_map.get(review_status, 'Review Required')
        
        context = {
            'inspection': inspection,
            'establishment_list': establishment_list,
            'reviewer': reviewer,
            'next_assignee': next_assignee,
            'review_status': review_status,
            'next_action': next_action,
            'law': inspection.law,
            'site_url': getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
        }
        
        html_message = render_to_string('emails/inspection_review_notification.html', context)
        plain_message = strip_tags(html_message)
        
        # Send to next reviewer
        email = EmailMessage(
            subject=subject,
            body=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[next_assignee.email],
        )
        email.content_subtype = 'html'  # Set content type to HTML
        email.extra_headers = {
            'X-Priority': '1',
            'X-MSMail-Priority': 'High',
            'Importance': 'High',
            'X-Mailer': 'IERMS System - Urgent Notification'
        }
        email.send(fail_silently=False)
        
        logger.info(f"Inspection review notification sent to {next_assignee.email} for {inspection.code}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send inspection review notification for {inspection.code}: {str(e)}")
        return False


def create_review_notification(recipient, inspection, reviewer, review_status, remarks=None):
    """
    Create in-app notification when inspection review is completed and forwarded (both compliant and non-compliant)
    """
    try:
        from notifications.models import Notification
        
        # Get establishment names
        establishment_names = [est.name for est in inspection.establishments.all()]
        establishment_list = ", ".join(establishment_names) if establishment_names else "No establishments"
        
        # Create notification message
        reviewer_name = f"{reviewer.first_name} {reviewer.last_name}" if reviewer.first_name else reviewer.email
        message = f"Inspection {inspection.code} for {establishment_list} has been reviewed by {reviewer_name} and forwarded to you."
        
        if remarks:
            message += f" Remarks: {remarks}"
        
        # Create notification
        notification = Notification.objects.create(
            recipient=recipient,
            sender=reviewer,
            notification_type='inspection_review',
            title='Inspection Review Required',
            message=message,
            related_object_type='inspection',
            related_object_id=inspection.id if hasattr(inspection, 'id') else None
        )
        
        logger.info(f"In-app review notification created for {recipient.email}")
        return notification
        
    except Exception as e:
        logger.error(f"Failed to create in-app review notification for {recipient.email}: {str(e)}")
        return None


def create_forward_notification(recipient, inspection, forwarded_by, remarks=None):
    """
    Create in-app notification when inspection is forwarded to a user
    """
    try:
        from notifications.models import Notification

        # Get establishment names
        establishment_names = [est.name for est in inspection.establishments.all()]
        establishment_list = ", ".join(establishment_names) if establishment_names else "No establishments"

        # Create notification message
        forwarded_by_name = f"{forwarded_by.first_name} {forwarded_by.last_name}" if forwarded_by.first_name else forwarded_by.email
        message = f"Inspection {inspection.code} for {establishment_list} has been forwarded to you by {forwarded_by_name}."

        if remarks:
            message += f" Remarks: {remarks}"

        # Create notification
        notification = Notification.objects.create(
            recipient=recipient,
            sender=forwarded_by,
            notification_type='inspection_forward',
            title='Inspection Forwarded to You',
            message=message,
            related_object_type='inspection',
            related_object_id=inspection.id if hasattr(inspection, 'id') else None
        )
        
        logger.info(f"In-app forward notification created for {recipient.email}")
        return notification

    except Exception as e:
        logger.error(f"Failed to create in-app forward notification for {recipient.email}: {str(e)}")
        return None


def create_return_notification(recipient, inspection, returned_by, return_status, remarks=None):
    """
    Create in-app notification when inspection is returned for additional action.
    """
    try:
        from notifications.models import Notification

        establishment_names = [est.name for est in inspection.establishments.all()]
        establishment_list = ", ".join(establishment_names) if establishment_names else "No establishments"

        returned_by_name = (
            f"{returned_by.first_name} {returned_by.last_name}".strip()
            if returned_by and returned_by.first_name
            else getattr(returned_by, "email", "System")
        )

        stage_map = {
            'MONITORING_COMPLETED_COMPLIANT': 'Monitoring Personnel',
            'MONITORING_COMPLETED_NON_COMPLIANT': 'Monitoring Personnel',
            'MONITORING_IN_PROGRESS': 'Monitoring Personnel',
            'UNIT_COMPLETED_COMPLIANT': 'Unit Head',
            'UNIT_COMPLETED_NON_COMPLIANT': 'Unit Head',
            'UNIT_IN_PROGRESS': 'Unit Head',
            'SECTION_COMPLETED_COMPLIANT': 'Section Chief',
            'SECTION_COMPLETED_NON_COMPLIANT': 'Section Chief',
            'SECTION_IN_PROGRESS': 'Section Chief',
        }
        stage_label = stage_map.get(return_status, 'previous stage owner')

        message = (
            f"Inspection {inspection.code} for {establishment_list} was returned by "
            f"{returned_by_name} to the {stage_label} for further action."
        )
        if remarks:
            message += f" Remarks: {remarks}"

        notification = Notification.objects.create(
            recipient=recipient,
            sender=returned_by,
            notification_type='inspection_return',
            title='Inspection Returned for Corrections',
            message=message,
            related_object_type='inspection',
            related_object_id=getattr(inspection, 'id', None)
        )

        logger.info(f"In-app return notification created for {recipient.email}")
        return notification

    except Exception as e:
        logger.error(f"Failed to create return notification for {recipient.email}: {str(e)}")
        return None


