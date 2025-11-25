"""
Normalized Inspection Form Models
Comprehensive database structure for inspection forms with proper normalization
"""
from django.db import models
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ValidationError
from establishments.models import Establishment


class InspectionFormTemplate(models.Model):
    """
    Template for inspection forms - defines the structure and fields
    """
    name = models.CharField(max_length=200, help_text="Template name (e.g., 'Environmental Inspection Form')")
    version = models.CharField(max_length=20, default="1.0.0")
    description = models.TextField(blank=True)
    applicable_laws = models.JSONField(default=list, help_text="List of applicable laws")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} v{self.version}"


class FormSection(models.Model):
    """
    Sections within an inspection form template
    """
    template = models.ForeignKey(InspectionFormTemplate, on_delete=models.CASCADE, related_name='sections')
    section_id = models.CharField(max_length=100, help_text="Unique identifier for the section")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    is_required = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['order', 'id']
        unique_together = ['template', 'section_id']
    
    def __str__(self):
        return f"{self.template.name} - {self.title}"


class FormField(models.Model):
    """
    Individual fields within form sections
    """
    FIELD_TYPES = [
        ('text', 'Text Input'),
        ('textarea', 'Text Area'),
        ('number', 'Number Input'),
        ('email', 'Email Input'),
        ('tel', 'Phone Number'),
        ('date', 'Date Input'),
        ('datetime-local', 'Date Time Input'),
        ('select', 'Select Dropdown'),
        ('checkbox', 'Single Checkbox'),
        ('checkbox_group', 'Checkbox Group'),
        ('radio', 'Radio Group'),
        ('permit_checklist', 'Permit Checklist'),
        ('compliance_checklist', 'Compliance Checklist'),
        ('system_checklist', 'System Checklist'),
    ]
    
    section = models.ForeignKey(FormSection, on_delete=models.CASCADE, related_name='fields')
    field_id = models.CharField(max_length=100, help_text="Unique identifier for the field")
    label = models.CharField(max_length=200)
    field_type = models.CharField(max_length=50, choices=FIELD_TYPES)
    placeholder = models.CharField(max_length=500, blank=True)
    help_text = models.TextField(blank=True)
    is_required = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    
    # Field configuration (JSON)
    field_config = models.JSONField(default=dict, help_text="Field-specific configuration (options, validation, etc.)")
    
    # Conditional logic
    conditional_logic = models.JSONField(default=dict, blank=True, help_text="Show/hide field based on other field values")
    
    class Meta:
        ordering = ['order', 'id']
        unique_together = ['section', 'field_id']
    
    def __str__(self):
        return f"{self.section.title} - {self.label}"


class InspectionFormInstance(models.Model):
    """
    Instance of an inspection form - the actual form filled out for an inspection
    """
    inspection = models.OneToOneField(
        'Inspection',
        on_delete=models.CASCADE,
        related_name='form_instance'
    )
    template = models.ForeignKey(InspectionFormTemplate, on_delete=models.CASCADE)
    
    # Form status
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('SUBMITTED', 'Submitted'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    
    # User tracking
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_forms'
    )
    last_modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='modified_forms'
    )
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Form for {self.inspection.code} - {self.get_status_display()}"


class FormFieldResponse(models.Model):
    """
    Individual field responses within a form instance
    """
    form_instance = models.ForeignKey(InspectionFormInstance, on_delete=models.CASCADE, related_name='responses')
    field = models.ForeignKey(FormField, on_delete=models.CASCADE)
    
    # Response data
    text_value = models.TextField(blank=True)
    number_value = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    date_value = models.DateTimeField(null=True, blank=True)
    boolean_value = models.BooleanField(null=True, blank=True)
    json_value = models.JSONField(default=dict, blank=True, help_text="For complex field types like checkboxes, lists, etc.")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['form_instance', 'field']
        ordering = ['field__section__order', 'field__order']
    
    def __str__(self):
        return f"{self.form_instance} - {self.field.label}"
    
    def get_value(self):
        """Get the appropriate value based on field type"""
        if self.field.field_type in ['text', 'textarea', 'email', 'tel']:
            return self.text_value
        elif self.field.field_type == 'number':
            return self.number_value
        elif self.field.field_type in ['date', 'datetime-local']:
            return self.date_value
        elif self.field.field_type == 'checkbox':
            return self.boolean_value
        else:
            return self.json_value
    
    def set_value(self, value):
        """Set the appropriate value based on field type"""
        if self.field.field_type in ['text', 'textarea', 'email', 'tel']:
            self.text_value = str(value) if value is not None else ''
        elif self.field.field_type == 'number':
            self.number_value = value
        elif self.field.field_type in ['date', 'datetime-local']:
            self.date_value = value
        elif self.field.field_type == 'checkbox':
            self.boolean_value = bool(value)
        else:
            self.json_value = value


class FormValidationRule(models.Model):
    """
    Validation rules for form fields
    """
    field = models.ForeignKey(FormField, on_delete=models.CASCADE, related_name='validation_rules')
    rule_type = models.CharField(max_length=50, help_text="Type of validation rule")
    rule_config = models.JSONField(default=dict, help_text="Configuration for the validation rule")
    error_message = models.CharField(max_length=500)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['id']
    
    def __str__(self):
        return f"{self.field.label} - {self.rule_type}"


class FormSubmission(models.Model):
    """
    Track form submissions and approvals
    """
    form_instance = models.OneToOneField(InspectionFormInstance, on_delete=models.CASCADE, related_name='submission')
    
    # Submission details
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='submitted_forms'
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    # Approval workflow
    APPROVAL_STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('REQUIRES_REVISION', 'Requires Revision'),
    ]
    approval_status = models.CharField(max_length=20, choices=APPROVAL_STATUS_CHOICES, default='PENDING')
    
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_forms'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_notes = models.TextField(blank=True)
    
    # Revision tracking
    revision_count = models.PositiveIntegerField(default=0)
    last_revision_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-submitted_at']
    
    def __str__(self):
        return f"Submission for {self.form_instance.inspection.code} - {self.get_approval_status_display()}"


class FormAuditLog(models.Model):
    """
    Audit log for form changes
    """
    form_instance = models.ForeignKey(InspectionFormInstance, on_delete=models.CASCADE, related_name='audit_logs')
    field = models.ForeignKey(FormField, on_delete=models.CASCADE, null=True, blank=True)
    
    # Change details
    ACTION_CHOICES = [
        ('CREATE', 'Created'),
        ('UPDATE', 'Updated'),
        ('DELETE', 'Deleted'),
        ('SUBMIT', 'Submitted'),
        ('APPROVE', 'Approved'),
        ('REJECT', 'Rejected'),
    ]
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    
    old_value = models.JSONField(default=dict, blank=True)
    new_value = models.JSONField(default=dict, blank=True)
    
    # User and timestamp
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    
    # Additional context
    notes = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-changed_at']
    
    def __str__(self):
        return f"{self.form_instance} - {self.action} by {self.changed_by}"


# Utility functions for form management
class FormManager:
    """
    Utility class for managing form instances and responses
    """
    
    @staticmethod
    def create_form_instance(inspection, template):
        """Create a new form instance for an inspection"""
        form_instance = InspectionFormInstance.objects.create(
            inspection=inspection,
            template=template,
            created_by=inspection.assigned_to,
            last_modified_by=inspection.assigned_to
        )
        return form_instance
    
    @staticmethod
    def get_form_data(form_instance):
        """Get all form data as a structured dictionary"""
        data = {
            'form_instance': form_instance,
            'sections': {}
        }
        
        for section in form_instance.template.sections.filter(is_active=True):
            section_data = {
                'section': section,
                'fields': {}
            }
            
            for field in section.fields.filter(is_active=True):
                try:
                    response = FormFieldResponse.objects.get(
                        form_instance=form_instance,
                        field=field
                    )
                    section_data['fields'][field.field_id] = {
                        'field': field,
                        'value': response.get_value(),
                        'response': response
                    }
                except FormFieldResponse.DoesNotExist:
                    section_data['fields'][field.field_id] = {
                        'field': field,
                        'value': None,
                        'response': None
                    }
            
            data['sections'][section.section_id] = section_data
        
        return data
    
    @staticmethod
    def save_field_response(form_instance, field_id, value, user=None):
        """Save or update a field response"""
        try:
            field = FormField.objects.get(
                section__template=form_instance.template,
                field_id=field_id
            )
        except FormField.DoesNotExist:
            raise ValidationError(f"Field {field_id} not found in template")
        
        response, created = FormFieldResponse.objects.get_or_create(
            form_instance=form_instance,
            field=field
        )
        
        # Store old value for audit log
        old_value = response.get_value()
        
        # Set new value
        response.set_value(value)
        response.save()
        
        # Update form instance
        form_instance.last_modified_by = user
        form_instance.updated_at = timezone.now()
        form_instance.save()
        
        # Create audit log
        FormAuditLog.objects.create(
            form_instance=form_instance,
            field=field,
            action='CREATE' if created else 'UPDATE',
            old_value=old_value,
            new_value=value,
            changed_by=user
        )
        
        return response
    
    @staticmethod
    def validate_form(form_instance):
        """Validate all required fields in the form"""
        errors = {}
        
        for section in form_instance.template.sections.filter(is_active=True):
            for field in section.fields.filter(is_active=True, is_required=True):
                try:
                    response = FormFieldResponse.objects.get(
                        form_instance=form_instance,
                        field=field
                    )
                    value = response.get_value()
                    
                    # Check if required field is empty
                    if value is None or (isinstance(value, str) and not value.strip()):
                        errors[field.field_id] = f"{field.label} is required"
                    
                    # Apply field-specific validation rules
                    for rule in field.validation_rules.filter(is_active=True):
                        if not FormManager._validate_field_rule(field, value, rule):
                            errors[field.field_id] = rule.error_message
                            
                except FormFieldResponse.DoesNotExist:
                    errors[field.field_id] = f"{field.label} is required"
        
        return errors
    
    @staticmethod
    def _validate_field_rule(field, value, rule):
        """Validate a specific field rule"""
        rule_type = rule.rule_config.get('type')
        rule_value = rule.rule_config.get('value')
        
        if rule_type == 'min_length' and isinstance(value, str):
            return len(value) >= rule_value
        elif rule_type == 'max_length' and isinstance(value, str):
            return len(value) <= rule_value
        elif rule_type == 'min' and isinstance(value, (int, float)):
            return value >= rule_value
        elif rule_type == 'max' and isinstance(value, (int, float)):
            return value <= rule_value
        elif rule_type == 'pattern' and isinstance(value, str):
            import re
            return bool(re.match(rule_value, value))
        
        return True
