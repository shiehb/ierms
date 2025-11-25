"""
Serializers for normalized inspection form models
"""
from rest_framework import serializers
from .models_normalized import (
    InspectionFormTemplate, FormSection, FormField, FormFieldResponse,
    InspectionFormInstance, FormSubmission, FormAuditLog, FormValidationRule
)


class FormValidationRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormValidationRule
        fields = ['id', 'rule_type', 'rule_config', 'error_message', 'is_active']


class FormFieldSerializer(serializers.ModelSerializer):
    validation_rules = FormValidationRuleSerializer(many=True, read_only=True)
    
    class Meta:
        model = FormField
        fields = [
            'id', 'field_id', 'label', 'field_type', 'placeholder', 'help_text',
            'is_required', 'order', 'field_config', 'conditional_logic', 'validation_rules'
        ]


class FormSectionSerializer(serializers.ModelSerializer):
    fields = FormFieldSerializer(many=True, read_only=True)
    
    class Meta:
        model = FormSection
        fields = [
            'id', 'section_id', 'title', 'description', 'order', 'is_required', 'is_active', 'fields'
        ]


class InspectionFormTemplateSerializer(serializers.ModelSerializer):
    sections = FormSectionSerializer(many=True, read_only=True)
    
    class Meta:
        model = InspectionFormTemplate
        fields = [
            'id', 'name', 'version', 'description', 'applicable_laws', 'is_active',
            'created_at', 'updated_at', 'sections'
        ]


class FormFieldResponseSerializer(serializers.ModelSerializer):
    field = FormFieldSerializer(read_only=True)
    field_id = serializers.CharField(write_only=True)
    value = serializers.SerializerMethodField()
    
    class Meta:
        model = FormFieldResponse
        fields = [
            'id', 'field', 'field_id', 'text_value', 'number_value', 'date_value',
            'boolean_value', 'json_value', 'value', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'field', 'created_at', 'updated_at']
    
    def get_value(self, obj):
        return obj.get_value()
    
    def create(self, validated_data):
        field_id = validated_data.pop('field_id')
        form_instance = validated_data.pop('form_instance')
        
        try:
            field = FormField.objects.get(
                section__template=form_instance.template,
                field_id=field_id
            )
        except FormField.DoesNotExist:
            raise serializers.ValidationError(f"Field {field_id} not found in template")
        
        # Get the value from the appropriate field based on field type
        value = validated_data.get('value')
        if value is not None:
            if field.field_type in ['text', 'textarea', 'email', 'tel']:
                validated_data['text_value'] = str(value)
            elif field.field_type == 'number':
                validated_data['number_value'] = value
            elif field.field_type in ['date', 'datetime-local']:
                validated_data['date_value'] = value
            elif field.field_type == 'checkbox':
                validated_data['boolean_value'] = bool(value)
            else:
                validated_data['json_value'] = value
        
        validated_data['field'] = field
        validated_data['form_instance'] = form_instance
        
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        field_id = validated_data.pop('field_id', None)
        value = validated_data.get('value')
        
        if value is not None:
            field = instance.field
            if field.field_type in ['text', 'textarea', 'email', 'tel']:
                validated_data['text_value'] = str(value)
            elif field.field_type == 'number':
                validated_data['number_value'] = value
            elif field.field_type in ['date', 'datetime-local']:
                validated_data['date_value'] = value
            elif field.field_type == 'checkbox':
                validated_data['boolean_value'] = bool(value)
            else:
                validated_data['json_value'] = value
        
        return super().update(instance, validated_data)


class InspectionFormInstanceSerializer(serializers.ModelSerializer):
    template = InspectionFormTemplateSerializer(read_only=True)
    template_id = serializers.IntegerField(write_only=True)
    responses = FormFieldResponseSerializer(many=True, read_only=True)
    form_data = serializers.SerializerMethodField()
    
    class Meta:
        model = InspectionFormInstance
        fields = [
            'id', 'inspection', 'template', 'template_id', 'status', 'form_data',
            'created_at', 'updated_at', 'completed_at', 'submitted_at',
            'created_by', 'last_modified_by', 'responses'
        ]
        read_only_fields = [
            'id', 'template', 'created_at', 'updated_at', 'completed_at', 'submitted_at',
            'created_by', 'last_modified_by', 'responses'
        ]
    
    def get_form_data(self, obj):
        """Get structured form data"""
        from .models_normalized import FormManager
        return FormManager.get_form_data(obj)
    
    def create(self, validated_data):
        template_id = validated_data.pop('template_id')
        inspection = validated_data['inspection']
        
        try:
            template = InspectionFormTemplate.objects.get(id=template_id, is_active=True)
        except InspectionFormTemplate.DoesNotExist:
            raise serializers.ValidationError("Invalid template ID")
        
        validated_data['template'] = template
        validated_data['created_by'] = inspection.assigned_to
        validated_data['last_modified_by'] = inspection.assigned_to
        
        return super().create(validated_data)


class FormSubmissionSerializer(serializers.ModelSerializer):
    form_instance = InspectionFormInstanceSerializer(read_only=True)
    submitted_by = serializers.StringRelatedField(read_only=True)
    approved_by = serializers.StringRelatedField(read_only=True)
    
    class Meta:
        model = FormSubmission
        fields = [
            'id', 'form_instance', 'submitted_by', 'submitted_at',
            'approval_status', 'approved_by', 'approved_at', 'approval_notes',
            'revision_count', 'last_revision_at'
        ]
        read_only_fields = [
            'id', 'form_instance', 'submitted_by', 'submitted_at',
            'approved_by', 'approved_at', 'revision_count', 'last_revision_at'
        ]


class FormAuditLogSerializer(serializers.ModelSerializer):
    field = FormFieldSerializer(read_only=True)
    changed_by = serializers.StringRelatedField(read_only=True)
    
    class Meta:
        model = FormAuditLog
        fields = [
            'id', 'form_instance', 'field', 'action', 'old_value', 'new_value',
            'changed_by', 'changed_at', 'notes', 'ip_address', 'user_agent'
        ]
        read_only_fields = [
            'id', 'form_instance', 'field', 'changed_by', 'changed_at',
            'ip_address', 'user_agent'
        ]


# Specialized serializers for form operations
class FormDataSerializer(serializers.Serializer):
    """Serializer for saving form data"""
    field_responses = serializers.DictField(
        child=serializers.JSONField(),
        help_text="Dictionary of field_id -> value mappings"
    )
    
    def validate_field_responses(self, value):
        """Validate field responses"""
        if not value:
            raise serializers.ValidationError("Field responses cannot be empty")
        return value


class FormValidationSerializer(serializers.Serializer):
    """Serializer for form validation results"""
    is_valid = serializers.BooleanField()
    errors = serializers.DictField(
        child=serializers.ListField(child=serializers.CharField()),
        required=False
    )
    warnings = serializers.DictField(
        child=serializers.ListField(child=serializers.CharField()),
        required=False
    )


class FormTemplateListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for template listing"""
    section_count = serializers.SerializerMethodField()
    field_count = serializers.SerializerMethodField()
    
    class Meta:
        model = InspectionFormTemplate
        fields = [
            'id', 'name', 'version', 'description', 'applicable_laws',
            'is_active', 'section_count', 'field_count', 'created_at', 'updated_at'
        ]
    
    def get_section_count(self, obj):
        return obj.sections.filter(is_active=True).count()
    
    def get_field_count(self, obj):
        return FormField.objects.filter(
            section__template=obj,
            section__is_active=True,
            is_active=True
        ).count()
