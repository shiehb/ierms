"""
Serializers for Refactored Inspection Models
"""
from rest_framework import serializers
from .models import (
    Inspection, InspectionForm, InspectionDocument, InspectionHistory,
    BillingRecord, NoticeOfViolation, NoticeOfOrder
)
from establishments.models import Establishment


class InspectionHistorySerializer(serializers.ModelSerializer):
    """Serializer for inspection history"""
    changed_by_name = serializers.SerializerMethodField()
    changed_by_level = serializers.SerializerMethodField()
    assigned_to_name = serializers.SerializerMethodField()
    assigned_to_level = serializers.SerializerMethodField()
    
    class Meta:
        model = InspectionHistory
        fields = [
            'id', 'inspection', 'previous_status', 'new_status',
            'changed_by', 'changed_by_name', 'changed_by_level',
            'assigned_to', 'assigned_to_name', 'assigned_to_level',
            'law', 'section', 'remarks', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_changed_by_name(self, obj):
        if obj.changed_by:
            return f"{obj.changed_by.first_name} {obj.changed_by.last_name}".strip() or obj.changed_by.email
        return None
    
    def get_changed_by_level(self, obj):
        return obj.changed_by.userlevel if obj.changed_by else None
    
    def get_assigned_to_name(self, obj):
        if obj.assigned_to:
            return f"{obj.assigned_to.first_name} {obj.assigned_to.last_name}".strip() or obj.assigned_to.email
        return None
    
    def get_assigned_to_level(self, obj):
        return obj.assigned_to.userlevel if obj.assigned_to else None


class InspectionDocumentSerializer(serializers.ModelSerializer):
    """Serializer for inspection documents"""
    uploaded_by_name = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = InspectionDocument
        fields = [
            'id', 'inspection_form', 'file', 'file_url', 'document_type',
            'description', 'uploaded_by', 'uploaded_by_name', 'uploaded_at'
        ]
        read_only_fields = ['id', 'uploaded_at']
    
    def get_uploaded_by_name(self, obj):
        if obj.uploaded_by:
            return f"{obj.uploaded_by.first_name} {obj.uploaded_by.last_name}".strip() or obj.uploaded_by.email
        return None
    
    def get_file_url(self, obj):
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
        return None


class NoticeOfViolationSerializer(serializers.ModelSerializer):
    """Serializer for Notice of Violation"""
    sent_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = NoticeOfViolation
        fields = [
            'inspection_form', 'sent_date', 'compliance_deadline',
            'violations', 'compliance_instructions', 'remarks',
            'sent_by', 'sent_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_sent_by_name(self, obj):
        if obj.sent_by:
            return f"{obj.sent_by.first_name} {obj.sent_by.last_name}".strip() or obj.sent_by.email
        return None


class NoticeOfOrderSerializer(serializers.ModelSerializer):
    """Serializer for Notice of Order"""
    sent_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = NoticeOfOrder
        fields = [
            'inspection_form', 'sent_date', 'violation_breakdown',
            'penalty_fees', 'payment_deadline', 'payment_instructions', 'remarks',
            'sent_by', 'sent_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_sent_by_name(self, obj):
        if obj.sent_by:
            return f"{obj.sent_by.first_name} {obj.sent_by.last_name}".strip() or obj.sent_by.email
        return None


class InspectionFormSerializer(serializers.ModelSerializer):
    """Serializer for inspection form"""
    documents = InspectionDocumentSerializer(many=True, read_only=True)
    nov = NoticeOfViolationSerializer(read_only=True)
    noo = NoticeOfOrderSerializer(read_only=True)
    inspected_by_name = serializers.SerializerMethodField()
    inspector_info = serializers.SerializerMethodField()
    checklist = serializers.SerializerMethodField()
    
    class Meta:
        model = InspectionForm
        fields = [
            'inspection', 'scheduled_at', 'checklist',
            'compliance_decision', 'violations_found', 'documents',
            'nov', 'noo', 'inspected_by', 'inspected_by_name', 'inspector_info',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'created_at', 'updated_at', 'inspected_by'
        ]
    
    def get_checklist(self, obj):
        """Get checklist with absolute URLs for signatures"""
        import copy
        checklist = copy.deepcopy(obj.checklist or {})
        
        # Convert relative signature URLs to absolute URLs
        if 'signatures' in checklist:
            request = self.context.get('request')
            if request:
                for slot_name, sig_data in checklist['signatures'].items():
                    if sig_data and isinstance(sig_data, dict) and 'url' in sig_data:
                        url = sig_data['url']
                        # Convert relative URL to absolute
                        if url and url.startswith('/'):
                            sig_data['url'] = request.build_absolute_uri(url)
        
        return checklist
    
    def get_inspected_by_name(self, obj):
        """Get the name of the user who inspected the form"""
        if obj.inspected_by:
            return f"{obj.inspected_by.first_name} {obj.inspected_by.last_name}".strip() or obj.inspected_by.email
        return None
    
    def get_inspector_info(self, obj):
        """Get formatted inspector information for display"""
        if not obj.inspected_by:
            return None
        
        # Safely get district if it exists on the user model (using getattr to handle removal)
        district = getattr(obj.inspected_by, 'district', None)
        # If district is a ForeignKey object, get its string representation
        if district and hasattr(district, 'name'):
            district = district.name
        elif district and hasattr(district, '__str__'):
            district = str(district)
        
        return {
            'name': self.get_inspected_by_name(obj),
            'level': obj.inspected_by.userlevel if obj.inspected_by else None,
            'section': obj.inspected_by.section if obj.inspected_by else None,
            'district': district,
            'inspected_at': obj.created_at  # Use form creation time as inspection time
        }
    
    def validate(self, data):
        """Ensure violations are provided if non-compliant"""
        if data.get('compliance_decision') == 'NON_COMPLIANT':
            if not data.get('violations_found'):
                raise serializers.ValidationError({
                    'violations_found': 'Violations must be specified for non-compliant inspections'
                })
        return data


class InspectionSerializer(serializers.ModelSerializer):
    """Main inspection serializer with all related data"""
    
    # Related data
    establishments = serializers.SerializerMethodField()
    establishments_detail = serializers.SerializerMethodField()
    form = InspectionFormSerializer(read_only=True)
    history = InspectionHistorySerializer(many=True, read_only=True)
    
    # User details
    created_by_name = serializers.SerializerMethodField()
    assigned_to_name = serializers.SerializerMethodField()
    assigned_to_level = serializers.SerializerMethodField()
    inspected_by_name = serializers.SerializerMethodField()
    
    # Status helpers
    simplified_status = serializers.SerializerMethodField()
    can_user_act = serializers.SerializerMethodField()
    available_actions = serializers.SerializerMethodField()

    # Return information
    return_remarks = serializers.SerializerMethodField()

    # Reinspection fields
    previous_inspection_code = serializers.SerializerMethodField()
    previous_inspection_date = serializers.SerializerMethodField()

    class Meta:
        model = Inspection
        fields = [
            'id', 'code', 'establishments', 'establishments_detail',
            'law', 'district', 'created_by', 'created_by_name',
            'assigned_to', 'assigned_to_name', 'assigned_to_level',
            'inspected_by_name',
            'current_status', 'simplified_status',
            'created_at', 'updated_at',
            'form', 'history',
            'can_user_act', 'available_actions',
            'return_remarks',
            'is_reinspection', 'previous_inspection',
            'previous_inspection_code', 'previous_inspection_date'
        ]
        read_only_fields = ['id', 'code', 'created_at', 'updated_at']
    
    def get_establishments(self, obj):
        """Get establishment IDs"""
        return list(obj.establishments.values_list('id', flat=True))
    
    def get_establishments_detail(self, obj):
        """Get detailed establishment information"""
        establishments = obj.establishments.all()
        return [{
            'id': est.id,
            'name': est.name,
            'nature_of_business': est.nature_of_business,
            'year_established': est.year_established,
            'province': est.province,
            'city': est.city,
            'barangay': est.barangay,
            'street_building': est.street_building,
            'postal_code': est.postal_code,
            'latitude': str(est.latitude),
            'longitude': str(est.longitude),
            'polygon': est.polygon,  # Add polygon data
        } for est in establishments]
    
    def get_created_by_name(self, obj):
        if obj.created_by:
            return f"{obj.created_by.first_name} {obj.created_by.last_name}".strip() or obj.created_by.email
        return None
    
    def get_assigned_to_name(self, obj):
        if obj.assigned_to:
            return f"{obj.assigned_to.first_name} {obj.assigned_to.last_name}".strip() or obj.assigned_to.email
        return None
    
    def get_assigned_to_level(self, obj):
        return obj.assigned_to.userlevel if obj.assigned_to else None
    
    def get_inspected_by_name(self, obj):
        """Get the name of the user who inspected this inspection"""
        if hasattr(obj, 'form') and obj.form and obj.form.inspected_by:
            inspector = obj.form.inspected_by
            return f"{inspector.first_name} {inspector.last_name}".strip() or inspector.email
        return None
    
    def get_simplified_status(self, obj):
        return obj.get_simplified_status()
    
    def get_can_user_act(self, obj):
        """Check if current user can act on this inspection"""
        request = self.context.get('request')
        if request and request.user:
            return obj.assigned_to == request.user
        return False

    def get_available_actions(self, obj):
        """Get available actions for current user"""
        request = self.context.get('request')
        if not request or not request.user:
            return []

        user = request.user
        status = obj.current_status
        
        
        # Define actions based on status and user level - 5 Button Strategy
        actions_map = {
            # Initial creation - Division Chief can assign to sections
            ('CREATED', 'Division Chief'): ['forward'],
            
            # Section Chief workflow
            ('SECTION_ASSIGNED', 'Section Chief'): ['inspect', 'forward'],
            ('SECTION_IN_PROGRESS', 'Section Chief'): ['continue'],
            ('SECTION_COMPLETED_COMPLIANT', 'Division Chief'): ['review'],  # NO forward, auto-assigned
            ('SECTION_COMPLETED_NON_COMPLIANT', 'Division Chief'): ['review'],  # NO forward, auto-assigned
            
            # Unit Head workflow
            ('UNIT_ASSIGNED', 'Unit Head'): ['inspect', 'forward', 'return_to_previous'],
            ('UNIT_IN_PROGRESS', 'Unit Head'): ['continue', 'forward'],
            ('UNIT_COMPLETED_COMPLIANT', 'Section Chief'): ['review'],  # NO forward, auto-assigned
            ('UNIT_COMPLETED_NON_COMPLIANT', 'Section Chief'): ['review'],  # NO forward, auto-assigned
            
            # Monitoring Personnel workflow
            ('MONITORING_ASSIGNED', 'Monitoring Personnel'): ['inspect'],
            ('MONITORING_ASSIGNED', 'Monitoring Personnel'): ['inspect', 'return_to_previous'],
            ('MONITORING_ASSIGNED', 'Unit Head'): ['forward', 'return_to_previous'],
            ('MONITORING_IN_PROGRESS', 'Monitoring Personnel'): ['continue'],
            ('MONITORING_COMPLETED_COMPLIANT', 'Unit Head'): ['review'],  # NO forward, auto-assigned
            ('MONITORING_COMPLETED_NON_COMPLIANT', 'Unit Head'): ['review'],  # NO forward, auto-assigned
            # Section Chief can review Monitoring completed when no Unit Head exists
            ('MONITORING_COMPLETED_COMPLIANT', 'Section Chief'): ['review'],  # When no Unit Head
            ('MONITORING_COMPLETED_NON_COMPLIANT', 'Section Chief'): ['review'],  # When no Unit Head
            
            # Review statuses (NO Forward button - removed as requested)
            ('UNIT_REVIEWED', 'Section Chief'): ['review', 'return_to_monitoring'],
            ('SECTION_REVIEWED', 'Division Chief'): ['review', 'return_to_unit'],
            # DIVISION_REVIEWED actions depend on compliance status - handled separately below
            ('DIVISION_REVIEWED', 'Division Chief'): ['return_to_section'],
            
            # Legal Unit actions
            ('LEGAL_REVIEW', 'Legal Unit'): ['review'],
            ('NOV_SENT', 'Legal Unit'): ['review'],
            ('NOO_SENT', 'Legal Unit'): ['review', 'close'],
        }
        
        key = (status, user.userlevel)
        available_actions = actions_map.get(key, [])
        
        # Special case: DIVISION_REVIEWED - actions handled via manual buttons (review only)
        if status == 'DIVISION_REVIEWED' and user.userlevel == 'Division Chief':
            return available_actions
        
        # Special case: Monitoring Personnel with MONITORING_ASSIGNED status
        if status == 'MONITORING_ASSIGNED' and user.userlevel == 'Monitoring Personnel':
            actions = ['inspect']
            if 'return_to_previous' in available_actions:
                actions.append('return_to_previous')
            return actions
        
        # Filter actions based on assignment status
        if obj.assigned_to == user:
            # User is assigned - can perform all available actions
            return available_actions
        else:
            # User is not assigned - allow stage owners to take over or perform review/final actions
            filtered_actions = []
            for action in available_actions:
                if action == 'inspect' and (
                    (status == 'SECTION_ASSIGNED' and user.userlevel == 'Section Chief') or
                    (status == 'UNIT_ASSIGNED' and user.userlevel == 'Unit Head') or
                    (status == 'MONITORING_ASSIGNED' and user.userlevel == 'Monitoring Personnel')
                ):
                    filtered_actions.append(action)
                elif action == 'forward' and user.userlevel in ['Section Chief', 'Unit Head', 'Division Chief']:
                    filtered_actions.append(action)
                elif action == 'review' and user.userlevel in ['Unit Head', 'Section Chief', 'Division Chief']:
                    # Unit Head, Section Chief, and Division Chief can review inspections even if not assigned (for review tab)
                    filtered_actions.append(action)
                elif action == 'return_to_previous' and (
                    (status == 'MONITORING_ASSIGNED' and user.userlevel == 'Unit Head') or
                    (status == 'UNIT_ASSIGNED' and user.userlevel == 'Unit Head')
                ):
                    filtered_actions.append(action)
                elif action in ['send_to_legal', 'close'] and user.userlevel == 'Division Chief':
                    # Division Chief can perform these actions even if not directly assigned
                    filtered_actions.append(action)
            
            return filtered_actions
    
    def get_return_remarks(self, obj):
        """Get the most recent return remarks - only called when needed"""
        # Only process if history is already loaded (avoids extra query)
        # Check if history has been prefetched or is already loaded
        if hasattr(obj, 'history'):
            # Try to get the most recent return entry
            # Use .all() if it's a queryset, otherwise treat as list
            try:
                if hasattr(obj.history, 'all'):
                    # It's a queryset - filter and get first
                    latest_return = obj.history.filter(
                        remarks__icontains='Returned'
                    ).order_by('-created_at').first()
                elif isinstance(obj.history, list):
                    # It's already a list - filter in Python
                    return_entries = [h for h in obj.history if h.remarks and 'Returned' in h.remarks]
                    if return_entries:
                        # Sort by created_at descending and get first
                        # Handle both dict and object formats
                        def get_created_at(entry):
                            if isinstance(entry, dict):
                                return entry.get('created_at', '')
                            elif hasattr(entry, 'created_at'):
                                return entry.created_at
                            return ''
                        return_entries_sorted = sorted(return_entries, key=get_created_at, reverse=True)
                        latest_return = return_entries_sorted[0] if return_entries_sorted else None
                    else:
                        latest_return = None
                else:
                    return None
                
                if latest_return:
                    # Handle both dict and object formats
                    if isinstance(latest_return, dict):
                        remarks = latest_return.get('remarks', '')
                    elif hasattr(latest_return, 'remarks'):
                        remarks = latest_return.remarks
                    else:
                        remarks = ''
                    
                    if remarks:
                        # Extract remarks after "Returned to X:" prefix if present
                        if ':' in remarks:
                            parts = remarks.split(':', 1)
                            return parts[1].strip() if len(parts) > 1 else remarks
                        return remarks
            except (AttributeError, KeyError, TypeError):
                # Handle any errors gracefully
                return None
        return None
    
    def get_previous_inspection_code(self, obj):
        """Get code of previous inspection if this is a reinspection"""
        if obj.previous_inspection:
            return obj.previous_inspection.code
        return None
    
    def get_previous_inspection_date(self, obj):
        """Get date of previous inspection if this is a reinspection"""
        if obj.previous_inspection:
            return obj.previous_inspection.created_at.isoformat() if obj.previous_inspection.created_at else None
        return None


class InspectionCreateSerializer(serializers.Serializer):
    """Serializer for creating inspections via wizard"""
    establishments = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        help_text='List of establishment IDs'
    )
    law = serializers.ChoiceField(
        choices=['PD-1586', 'RA-6969', 'RA-8749', 'RA-9275', 'RA-9003']
    )
    scheduled_at = serializers.DateTimeField(required=False, allow_null=True)
    reinspection_schedule_id = serializers.IntegerField(required=False, allow_null=True, help_text='ID of reinspection schedule if this is a reinspection')
    
    def validate_establishments(self, value):
        """Validate that all establishment IDs exist"""
        existing_ids = set(Establishment.objects.filter(id__in=value).values_list('id', flat=True))
        invalid_ids = set(value) - existing_ids
        if invalid_ids:
            raise serializers.ValidationError(
                f"Invalid establishment IDs: {', '.join(map(str, invalid_ids))}"
            )
        return value
    
    def create(self, validated_data):
        """Create inspection with form"""
        establishment_ids = validated_data.pop('establishments')
        scheduled_at = validated_data.pop('scheduled_at', None)
        reinspection_schedule_id = validated_data.pop('reinspection_schedule_id', None)
        
        # Get request user
        request = self.context.get('request')
        user = request.user if request else None
        
        # Handle reinspection schedule if provided
        previous_inspection = None
        is_reinspection = False
        
        if reinspection_schedule_id:
            # Priority 1: If reinspection_schedule_id is provided, use it
            try:
                from .models import ReinspectionSchedule
                schedule = ReinspectionSchedule.objects.get(id=reinspection_schedule_id)
                previous_inspection = schedule.original_inspection
                is_reinspection = True
                # Update schedule status to SCHEDULED
                schedule.status = 'SCHEDULED'
                schedule.save()
            except ReinspectionSchedule.DoesNotExist:
                pass  # Invalid schedule ID, continue without reinspection link
        else:
            # Priority 2: Auto-detect reinspection by checking establishment history
            # Find the most recent closed inspection for any of the establishments
            # that matches the same law (if specified)
            from .models import Inspection
            law_filter = validated_data.get('law')
            
            # Query for closed inspections with matching establishments
            closed_inspections = Inspection.objects.filter(
                establishments__id__in=establishment_ids,
                current_status__in=['CLOSED_COMPLIANT', 'CLOSED_NON_COMPLIANT']
            )
            
            # If law is specified, filter by law as well
            if law_filter:
                closed_inspections = closed_inspections.filter(law=law_filter)
            
            # Get the most recent closed inspection
            previous_inspection = closed_inspections.order_by('-updated_at').first()
            
            if previous_inspection:
                is_reinspection = True
        
        # Create inspection
        inspection = Inspection.objects.create(
            law=validated_data['law'],
            created_by=user,
            current_status='CREATED',
            previous_inspection=previous_inspection,
            is_reinspection=is_reinspection
        )
        
        # Add establishments
        inspection.establishments.set(establishment_ids)
        
        # Determine district from first establishment
        first_establishment = Establishment.objects.get(id=establishment_ids[0])
        from inspections.regions import get_district_by_city
        district = get_district_by_city(first_establishment.province, first_establishment.city)
        if district:
            inspection.district = f"{first_establishment.province} - {district}"
            inspection.save()
        
        # Create inspection form
        InspectionForm.objects.create(
            inspection=inspection,
            scheduled_at=scheduled_at
        )
        
        # Transition to SECTION_ASSIGNED and auto-assign
        if user and user.userlevel == 'Division Chief':
            inspection.current_status = 'SECTION_ASSIGNED'
            inspection.auto_assign_personnel()
            inspection.save()
            
            # Log history
            InspectionHistory.objects.create(
                inspection=inspection,
                previous_status='CREATED',
                new_status='SECTION_ASSIGNED',
                changed_by=user,
                remarks='Inspection created and assigned to Section Chief'
            )
            
            # Send notifications to assigned Section Chief
            if inspection.assigned_to:
                from notifications.models import Notification
                from .utils import send_inspection_assignment_notification
                import logging
                
                logger = logging.getLogger(__name__)
                
                # Get establishment names for notification message
                establishment_names = [est.name for est in inspection.establishments.all()]
                establishment_list = ", ".join(establishment_names) if establishment_names else "No establishments"
                
                # Create system notification
                Notification.objects.create(
                    recipient=inspection.assigned_to,
                    sender=user,
                    notification_type='new_inspection',
                    title='New Inspection Assignment',
                    message=f'You have been assigned inspection {inspection.code} for {establishment_list} under {inspection.law}. Please review and take action.'
                )
                
                # Send email notification
                try:
                    send_inspection_assignment_notification(inspection.assigned_to, inspection)
                    logger.info(f"Notification sent to {inspection.assigned_to.email} for inspection {inspection.code}")
                except Exception as e:
                    # Don't fail inspection creation if email fails
                    logger.error(f"Failed to send email notification for inspection {inspection.code}: {str(e)}")
        
        return inspection


class InspectionActionSerializer(serializers.Serializer):
    """Serializer for inspection actions (assign, start, complete, forward, review)"""
    remarks = serializers.CharField(required=False, allow_blank=True)
    
    # For complete action (monitoring)
    compliance_decision = serializers.ChoiceField(
        choices=['COMPLIANT', 'NON_COMPLIANT', 'PARTIALLY_COMPLIANT'],
        required=False
    )
    violations_found = serializers.ListField(
        child=serializers.CharField(allow_blank=True),
        required=False,
        allow_empty=True
    )
    findings_summary = serializers.CharField(required=False, allow_blank=True)
    
    # For form data
    form_data = serializers.JSONField(required=False)


class NOVSerializer(serializers.Serializer):
    """Serializer for sending Notice of Violation"""
    recipient_email = serializers.EmailField(required=True,
        help_text='Email address of NOV recipient')
    recipient_name = serializers.CharField(required=False, allow_blank=True,
        help_text='Recipient name to personalize NOV email')
    contact_person = serializers.CharField(required=False, allow_blank=True,
        help_text='Contact person included in email')
    email_subject = serializers.CharField(required=False, allow_blank=True,
        help_text='Subject line for NOV email')
    email_body = serializers.CharField(required=False, allow_blank=True,
        help_text='Body content for NOV email')
    violations = serializers.CharField(required=True, 
        help_text='Detailed list of violations found')
    compliance_instructions = serializers.CharField(required=True,
        help_text='Required compliance actions')
    compliance_deadline = serializers.DateTimeField(required=True,
        help_text='Deadline for establishment to comply')
    remarks = serializers.CharField(required=False, allow_blank=True,
        help_text='Additional remarks')


class NOOSerializer(serializers.Serializer):
    """Serializer for sending Notice of Order with billing"""
    recipient_email = serializers.EmailField(required=True,
        help_text='Email address of NOO recipient')
    recipient_name = serializers.CharField(required=False, allow_blank=True,
        help_text='Recipient name to personalize NOO email')
    contact_person = serializers.CharField(required=False, allow_blank=True,
        help_text='Contact person included in email')
    email_subject = serializers.CharField(required=False, allow_blank=True,
        help_text='Subject line for NOO email')
    email_body = serializers.CharField(required=False, allow_blank=True,
        help_text='Body content for NOO email')
    violation_breakdown = serializers.CharField(required=True,
        help_text='Detailed breakdown of violations')
    penalty_fees = serializers.DecimalField(max_digits=10, decimal_places=2, 
        required=True, help_text='Total penalty amount')
    payment_deadline = serializers.DateField(required=True,
        help_text='Deadline for penalty payment')
    payment_instructions = serializers.CharField(required=False, allow_blank=True,
        help_text='Instructions for payment')
    remarks = serializers.CharField(required=False, allow_blank=True,
        help_text='Additional remarks')
    billing_items = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        help_text='List of individual violation line items'
    )


class BillingRecordSerializer(serializers.ModelSerializer):
    """Serializer for Billing Records"""
    inspection_code = serializers.CharField(source='inspection.code', read_only=True)
    issued_by_name = serializers.SerializerMethodField()
    payment_confirmed_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = BillingRecord
        fields = [
            'id', 'billing_code', 'inspection', 'inspection_code',
            'establishment', 'establishment_name', 'contact_person',
            'related_law', 'billing_type',
            'description', 'amount', 'due_date', 'recommendations',
            'issued_by', 'issued_by_name', 'sent_date',
            'payment_status', 'payment_date', 'payment_reference',
            'payment_notes', 'payment_confirmed_by', 'payment_confirmed_by_name',
            'payment_confirmed_at', 'legal_action',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'billing_code', 'sent_date',
            'payment_confirmed_by', 'payment_confirmed_by_name', 'payment_confirmed_at',
            'created_at', 'updated_at'
        ]
    
    def get_issued_by_name(self, obj):
        if obj.issued_by:
            return f"{obj.issued_by.first_name} {obj.issued_by.last_name}".strip() or obj.issued_by.email
        return None
    
    def get_payment_confirmed_by_name(self, obj):
        if obj.payment_confirmed_by:
            return f"{obj.payment_confirmed_by.first_name} {obj.payment_confirmed_by.last_name}".strip() or obj.payment_confirmed_by.email
        return None


class LegalReportSerializer(serializers.ModelSerializer):
    """Serializer for Legal Report Generation with combined data"""
    inspection_code = serializers.CharField(source='inspection.code', read_only=True)
    inspection_type = serializers.SerializerMethodField()
    issued_by_name = serializers.SerializerMethodField()
    compliance_status = serializers.SerializerMethodField()
    has_nov = serializers.SerializerMethodField()
    has_noo = serializers.SerializerMethodField()
    nov_sent_date = serializers.SerializerMethodField()
    noo_sent_date = serializers.SerializerMethodField()
    days_overdue = serializers.SerializerMethodField()
    assigned_legal_officer = serializers.SerializerMethodField()
    
    class Meta:
        model = BillingRecord
        fields = [
            'id', 'billing_code', 'inspection', 'inspection_code', 'inspection_type',
            'establishment', 'establishment_name', 'contact_person',
            'related_law', 'billing_type',
            'description', 'amount', 'due_date', 'recommendations',
            'issued_by', 'issued_by_name', 'sent_date',
            'payment_status', 'payment_date', 'payment_reference',
            'payment_notes', 'legal_action',
            'compliance_status', 'has_nov', 'has_noo',
            'nov_sent_date', 'noo_sent_date',
            'days_overdue', 'assigned_legal_officer',
            'created_at', 'updated_at'
        ]
    
    def get_inspection_type(self, obj):
        """Derive inspection type from inspection status"""
        if obj.inspection:
            status = obj.inspection.current_status
            if 'SECTION' in status:
                return 'Initial Inspection'
            elif 'UNIT' in status:
                return 'Re-inspection'
            elif 'MONITORING' in status:
                return 'Monitoring'
            return 'Unit Inspection'
        return 'N/A'
    
    def get_issued_by_name(self, obj):
        if obj.issued_by:
            return f"{obj.issued_by.first_name} {obj.issued_by.last_name}".strip() or obj.issued_by.email
        return None
    
    def get_compliance_status(self, obj):
        """Get compliance status from inspection form"""
        if obj.inspection and hasattr(obj.inspection, 'form') and obj.inspection.form:
            return obj.inspection.form.compliance_decision or 'PENDING'
        return 'PENDING'
    
    def get_has_nov(self, obj):
        """Check if NOV was sent"""
        if obj.inspection and hasattr(obj.inspection, 'form') and obj.inspection.form:
            return hasattr(obj.inspection.form, 'nov') and obj.inspection.form.nov is not None
        return False
    
    def get_has_noo(self, obj):
        """Check if NOO was sent"""
        if obj.inspection and hasattr(obj.inspection, 'form') and obj.inspection.form:
            return hasattr(obj.inspection.form, 'noo') and obj.inspection.form.noo is not None
        return False
    
    def get_nov_sent_date(self, obj):
        """Get NOV sent date"""
        if obj.inspection and hasattr(obj.inspection, 'form') and obj.inspection.form:
            if hasattr(obj.inspection.form, 'nov') and obj.inspection.form.nov:
                return obj.inspection.form.nov.sent_date
        return None
    
    def get_noo_sent_date(self, obj):
        """Get NOO sent date"""
        if obj.inspection and hasattr(obj.inspection, 'form') and obj.inspection.form:
            if hasattr(obj.inspection.form, 'noo') and obj.inspection.form.noo:
                return obj.inspection.form.noo.sent_date
        return None
    
    def get_days_overdue(self, obj):
        """Calculate days overdue for payment"""
        from django.utils import timezone
        if obj.payment_status == 'UNPAID' and obj.due_date:
            today = timezone.now().date()
            if today > obj.due_date:
                return (today - obj.due_date).days
        return 0
    
    def get_assigned_legal_officer(self, obj):
        """Get assigned legal officer"""
        if obj.issued_by:
            return f"{obj.issued_by.first_name} {obj.issued_by.last_name}".strip() or obj.issued_by.email
        return None


class DivisionReportSerializer(serializers.ModelSerializer):
    """Serializer for Division Report Generation with inspection data"""
    establishment_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    assigned_to_name = serializers.SerializerMethodField()
    assigned_to_level = serializers.SerializerMethodField()
    simplified_status = serializers.SerializerMethodField()
    compliance_status = serializers.SerializerMethodField()
    has_nov = serializers.SerializerMethodField()
    has_noo = serializers.SerializerMethodField()
    nov_sent_date = serializers.SerializerMethodField()
    noo_sent_date = serializers.SerializerMethodField()
    inspected_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Inspection
        fields = [
            'id', 'code', 'establishment_name', 'law', 'district',
            'created_by', 'created_by_name', 'assigned_to', 'assigned_to_name', 'assigned_to_level',
            'inspected_by_name', 'current_status', 'simplified_status',
            'compliance_status', 'has_nov', 'has_noo',
            'nov_sent_date', 'noo_sent_date',
            'created_at', 'updated_at'
        ]
    
    def get_created_by_name(self, obj):
        if obj.created_by:
            return f"{obj.created_by.first_name} {obj.created_by.last_name}".strip() or obj.created_by.email
        return None
    
    def get_assigned_to_name(self, obj):
        if obj.assigned_to:
            return f"{obj.assigned_to.first_name} {obj.assigned_to.last_name}".strip() or obj.assigned_to.email
        return None
    
    def get_assigned_to_level(self, obj):
        return obj.assigned_to.userlevel if obj.assigned_to else None
    
    def get_simplified_status(self, obj):
        return obj.get_simplified_status()
    
    def get_establishment_name(self, obj):
        """Get establishment name from related establishments"""
        if obj.establishments.exists():
            return obj.establishments.first().name
        return None
    
    def get_compliance_status(self, obj):
        """Get compliance status from inspection form"""
        if hasattr(obj, 'form') and obj.form:
            return obj.form.compliance_decision or 'PENDING'
        return 'PENDING'
    
    def get_has_nov(self, obj):
        """Check if NOV was sent"""
        if hasattr(obj, 'form') and obj.form and hasattr(obj.form, 'nov'):
            return obj.form.nov is not None
        return False
    
    def get_has_noo(self, obj):
        """Check if NOO was sent"""
        if hasattr(obj, 'form') and obj.form and hasattr(obj.form, 'noo'):
            return obj.form.noo is not None
        return False
    
    def get_nov_sent_date(self, obj):
        """Get NOV sent date"""
        if hasattr(obj, 'form') and obj.form and hasattr(obj.form, 'nov') and obj.form.nov:
            return obj.form.nov.sent_date
        return None
    
    def get_noo_sent_date(self, obj):
        """Get NOO sent date"""
        if hasattr(obj, 'form') and obj.form and hasattr(obj.form, 'noo') and obj.form.noo:
            return obj.form.noo.sent_date
        return None
    
    def get_inspected_by_name(self, obj):
        """Get the name of the user who inspected this inspection"""
        if hasattr(obj, 'form') and obj.form and obj.form.inspected_by:
            inspector = obj.form.inspected_by
            return f"{inspector.first_name} {inspector.last_name}".strip() or inspector.email
        return None


class SignatureUploadSerializer(serializers.Serializer):
    """Serializer for signature image upload"""
    slot = serializers.ChoiceField(
        choices=[
            ('submitted', 'Submitted'),
            ('review_unit', 'Review Unit'),
            ('review_section', 'Review Section'),
            ('approve_division', 'Approve Division'),
        ],
        required=True,
        help_text='Signature slot designation'
    )
    file = serializers.ImageField(
        required=True,
        help_text='Signature image file (PNG or JPEG, max 2MB)'
    )
    
    def validate_file(self, value):
        """Validate signature image file"""
        import os
        
        # Check file size (2MB max)
        if value.size > 2 * 1024 * 1024:
            raise serializers.ValidationError("File size must not exceed 2MB")
        
        # Check file extension
        valid_extensions = ['.png', '.jpg', '.jpeg']
        ext = os.path.splitext(value.name)[1].lower()
        if ext not in valid_extensions:
            raise serializers.ValidationError("Only PNG and JPEG images are allowed")
        
        # Check content type
        valid_types = ['image/png', 'image/jpeg', 'image/jpg']
        if value.content_type not in valid_types:
            raise serializers.ValidationError("Invalid file type. Only PNG and JPEG images are allowed")
        
        return value


class RecommendationSerializer(serializers.Serializer):
    """Serializer for inspection recommendations"""
    id = serializers.UUIDField(read_only=True)
    text = serializers.CharField(max_length=1000, required=True)
    priority = serializers.ChoiceField(
        choices=['HIGH', 'MEDIUM', 'LOW'],
        default='MEDIUM'
    )
    category = serializers.ChoiceField(
        choices=['COMPLIANCE', 'ENVIRONMENTAL', 'SAFETY', 'OPERATIONAL', 'OTHER'],
        default='COMPLIANCE'
    )
    status = serializers.ChoiceField(
        choices=['PENDING', 'IMPLEMENTED', 'NOT_APPLICABLE'],
        default='PENDING',
        required=False
    )
    created_by = serializers.IntegerField(read_only=True)
    created_by_name = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    
    def validate_text(self, value):
        """Ensure recommendation text is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("Recommendation text cannot be empty")
        return value.strip()
    