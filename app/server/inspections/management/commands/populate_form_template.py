"""
Management command to populate form template from JSON configuration
"""
import json
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from inspections.models_normalized import (
    InspectionFormTemplate, FormSection, FormField, FormValidationRule
)


class Command(BaseCommand):
    help = 'Populate inspection form template from JSON configuration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--json-file',
            type=str,
            help='Path to JSON configuration file',
            default='src/constants/inspectionform/formConfig.json'
        )
        parser.add_argument(
            '--template-name',
            type=str,
            help='Name for the form template',
            default='Environmental Inspection Form'
        )
        parser.add_argument(
            '--version',
            type=str,
            help='Version for the form template',
            default='1.0.0'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update existing template'
        )

    def handle(self, *args, **options):
        json_file = options['json_file']
        template_name = options['template_name']
        version = options['version']
        force = options['force']

        # Get the full path to the JSON file
        if not os.path.isabs(json_file):
            json_file = os.path.join(settings.BASE_DIR, json_file)

        if not os.path.exists(json_file):
            self.stdout.write(
                self.style.ERROR(f'JSON file not found: {json_file}')
            )
            return

        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            self.stdout.write(
                self.style.ERROR(f'Invalid JSON file: {e}')
            )
            return

        # Create or update template
        template, created = InspectionFormTemplate.objects.get_or_create(
            name=template_name,
            defaults={
                'version': version,
                'description': config.get('formMetadata', {}).get('description', ''),
                'applicable_laws': config.get('formMetadata', {}).get('applicableLaws', []),
            }
        )

        if not created and not force:
            self.stdout.write(
                self.style.WARNING(f'Template "{template_name}" already exists. Use --force to update.')
            )
            return

        if not created and force:
            # Update existing template
            template.version = version
            template.description = config.get('formMetadata', {}).get('description', '')
            template.applicable_laws = config.get('formMetadata', {}).get('applicableLaws', [])
            template.save()
            
            # Clear existing sections and fields
            template.sections.all().delete()
            self.stdout.write(
                self.style.SUCCESS(f'Updated template "{template_name}"')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'Created template "{template_name}"')
            )

        # Create sections and fields
        sections_data = config.get('formSections', [])
        for section_order, section_data in enumerate(sections_data):
            section = FormSection.objects.create(
                template=template,
                section_id=section_data['id'],
                title=section_data['title'],
                description=section_data.get('description', ''),
                order=section_order,
                is_required=section_data.get('required', True),
            )

            # Create fields for this section
            fields_data = section_data.get('fields', [])
            for field_order, field_data in enumerate(fields_data):
                field = FormField.objects.create(
                    section=section,
                    field_id=field_data['id'],
                    label=field_data['label'],
                    field_type=field_data['type'],
                    placeholder=field_data.get('placeholder', ''),
                    help_text=field_data.get('help_text', ''),
                    is_required=field_data.get('required', False),
                    order=field_order,
                    field_config=self._build_field_config(field_data),
                    conditional_logic=field_data.get('conditional', {}),
                )

                # Create validation rules
                self._create_validation_rules(field, field_data)

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully populated template with {len(sections_data)} sections'
            )
        )

    def _build_field_config(self, field_data):
        """Build field configuration based on field type"""
        config = {}

        if field_data['type'] == 'select':
            config['options'] = field_data.get('options', [])
        elif field_data['type'] == 'checkbox_group':
            config['options'] = field_data.get('options', [])
        elif field_data['type'] == 'permit_checklist':
            config['permit_types'] = field_data.get('permit_types', [])
        elif field_data['type'] == 'compliance_checklist':
            config['compliance_categories'] = field_data.get('compliance_categories', [])
        elif field_data['type'] == 'system_checklist':
            config['systems'] = field_data.get('systems', [])
        elif field_data['type'] == 'number':
            config['min'] = field_data.get('min')
            config['max'] = field_data.get('max')
        elif field_data['type'] == 'textarea':
            config['rows'] = field_data.get('rows', 3)

        # Add validation configuration
        if 'validation' in field_data:
            config['validation'] = field_data['validation']

        return config

    def _create_validation_rules(self, field, field_data):
        """Create validation rules for a field"""
        # Required field validation
        if field_data.get('required', False):
            FormValidationRule.objects.create(
                field=field,
                rule_type='required',
                rule_config={'type': 'required'},
                error_message=f'{field.label} is required'
            )

        # Field-specific validation
        if 'validation' in field_data:
            validation = field_data['validation']
            
            if 'pattern' in validation:
                FormValidationRule.objects.create(
                    field=field,
                    rule_type='pattern',
                    rule_config={
                        'type': 'pattern',
                        'value': validation['pattern']
                    },
                    error_message=validation.get('message', f'{field.label} format is invalid')
                )

        # Number field validation
        if field_data['type'] == 'number':
            if 'min' in field_data:
                FormValidationRule.objects.create(
                    field=field,
                    rule_type='min',
                    rule_config={
                        'type': 'min',
                        'value': field_data['min']
                    },
                    error_message=f'{field.label} must be at least {field_data["min"]}'
                )
            
            if 'max' in field_data:
                FormValidationRule.objects.create(
                    field=field,
                    rule_type='max',
                    rule_config={
                        'type': 'max',
                        'value': field_data['max']
                    },
                    error_message=f'{field.label} must be at most {field_data["max"]}'
                )
