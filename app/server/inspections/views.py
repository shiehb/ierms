"""
Refactored Inspection Views with Complete Workflow
"""
import logging

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q, Exists, OuterRef, Prefetch
from django.contrib.auth import get_user_model
from django.utils import timezone

from audit.constants import AUDIT_ACTIONS, AUDIT_MODULES
from audit.models import ActivityLog
from audit.serializers import ActivityLogSerializer
from audit.utils import log_activity

from .models import Inspection, InspectionForm, InspectionDocument, InspectionHistory, NoticeOfViolation, NoticeOfOrder, BillingRecord
from .serializers import (
    InspectionSerializer, InspectionCreateSerializer, InspectionFormSerializer,
    InspectionHistorySerializer, InspectionDocumentSerializer,
    InspectionActionSerializer, NOVSerializer, NOOSerializer, BillingRecordSerializer,
    SignatureUploadSerializer, RecommendationSerializer, LegalReportSerializer, DivisionReportSerializer
)
from .utils import (
    send_inspection_forward_notification,
    create_forward_notification,
    create_return_notification,
    send_notice_email,
)

User = get_user_model()
USER_HAS_DISTRICT = any(field.name == 'district' for field in User._meta.get_fields())

logger = logging.getLogger(__name__)


def capture_inspector_info(form, user):
    """Capture inspector information on first form fill-out"""
    if form.inspected_by is None and user:
        form.inspected_by = user
        return True  # Indicates this was the first fill-out
    return False  # Not first fill-out


def audit_inspection_event(user, inspection, action, description, request, metadata=None):
    """Helper to standardize inspection audit logging."""
    reference = getattr(inspection, "reference_no", None) or getattr(inspection, "reference_number", None)
    payload = {
        "entity_id": inspection.id,
        "entity_name": reference or f"Inspection #{inspection.id}",
        "status": "success",
        "current_status": inspection.current_status,
        "assigned_to": getattr(inspection.assigned_to, "email", None),
    }
    if metadata:
        payload.update(metadata)

    log_activity(
        user,
        action,
        module=AUDIT_MODULES["INSPECTIONS"],
        description=description,
        metadata=payload,
        request=request,
    )


class InspectionViewSet(viewsets.ModelViewSet):
    """
    Complete Inspection ViewSet with workflow state machine
    """
    queryset = Inspection.objects.all()
    serializer_class = InspectionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'create':
            return InspectionCreateSerializer
        return InspectionSerializer
    
    def create(self, request, *args, **kwargs):
        """Create inspection using InspectionCreateSerializer"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        inspection = serializer.save()
        
        # Audit trail for inspection creation
        establishment_ids = request.data.get('establishments', [])
        establishment_names = [est.name for est in inspection.establishments.all()]
        
        audit_inspection_event(
            request.user,
            inspection,
            AUDIT_ACTIONS["CREATE"],
            f"{request.user.email} created inspection {inspection.code}",
            request,
            metadata={
                "action": "inspection_creation",
                "law": inspection.law,
                "establishment_ids": establishment_ids,
                "establishment_names": establishment_names,
                "establishment_count": len(establishment_ids),
                "scheduled_at": request.data.get('scheduled_at'),
                "initial_status": inspection.current_status,
                "district": inspection.district,
            },
        )
        
        # Create initial history entry if not already created by serializer
        if not InspectionHistory.objects.filter(inspection=inspection, previous_status__isnull=True).exists():
            InspectionHistory.objects.create(
                inspection=inspection,
                previous_status=None,
                new_status=inspection.current_status,
                changed_by=request.user,
                law=inspection.law,
                section=getattr(request.user, 'section', None),
                remarks=f'Inspection {inspection.code} created with {len(establishment_ids)} establishment(s)'
            )
        
        # Return the created inspection using the main serializer
        response_serializer = InspectionSerializer(inspection, context={'request': request})
        headers = self.get_success_headers(response_serializer.data)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
    def update(self, request, *args, **kwargs):
        """Update inspection with access control validation"""
        inspection = self.get_object()
        user = request.user
        
        # Check if user is trying to update recommendation
        if 'recommendation' in request.data:
            # Only Division Chief can update recommendations
            if user.userlevel != 'Division Chief':
                return Response(
                    {'error': 'Only Division Chief can update recommendations'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Update the recommendation in the form's checklist
            form, created = InspectionForm.objects.get_or_create(inspection=inspection)
            if not form.checklist:
                form.checklist = {}
            
            form.checklist['recommendationState'] = request.data['recommendation']
            form.save()
            
            return Response({
                'message': 'Recommendation updated successfully',
                'inspection': self.get_serializer(inspection).data
            })
        
        # Call the parent update method for other fields
        return super().update(request, *args, **kwargs)
    
    def list(self, request, *args, **kwargs):
        """List inspections with pagination"""
        queryset = self.filter_queryset(self.get_queryset())
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    def get_queryset(self):
        """Filter inspections based on user role and tab"""
        user = self.request.user
        queryset = super().get_queryset()
        
        # Get filter parameters
        tab = self.request.query_params.get('tab')
        status_filter = self.request.query_params.get('status')
        assigned_to_me = self.request.query_params.get('assigned_to_me') == 'true'
        created_by_me = self.request.query_params.get('created_by_me') == 'true'
        search = self.request.query_params.get('search')
        
        # Role-based filtering
        if user.userlevel == 'Admin':
            # Admin sees all inspections but can filter by workflow stage tabs
            final_statuses = [
                'SECTION_COMPLETED_COMPLIANT',
                'SECTION_COMPLETED_NON_COMPLIANT',
                'UNIT_COMPLETED_COMPLIANT',
                'UNIT_COMPLETED_NON_COMPLIANT',
                'MONITORING_COMPLETED_COMPLIANT',
                'MONITORING_COMPLETED_NON_COMPLIANT',
                'SECTION_REVIEWED',
                'UNIT_REVIEWED',
                'DIVISION_REVIEWED',
                'LEGAL_REVIEW',
                'NOV_SENT',
                'NOO_SENT',
                'CLOSED_COMPLIANT',
                'CLOSED_NON_COMPLIANT'
            ]
            if tab == 'compliant':
                queryset = queryset.filter(
                    form__compliance_decision='COMPLIANT',
                    current_status='CLOSED_COMPLIANT'
                )
            elif tab == 'non_compliant':
                queryset = queryset.filter(
                    form__compliance_decision__in=['NON_COMPLIANT', 'PARTIALLY_COMPLIANT'],
                    current_status='CLOSED_NON_COMPLIANT'
                )
            # All other tabs fall back to the unfiltered queryset for Admin
        elif user.userlevel == 'Division Chief':
            queryset = self._filter_division_chief(queryset, user, tab)
        elif user.userlevel == 'Section Chief':
            queryset = self._filter_section_chief(queryset, user, tab)
        elif user.userlevel == 'Unit Head':
            queryset = self._filter_unit_head(queryset, user, tab)
        elif user.userlevel == 'Monitoring Personnel':
            queryset = self._filter_monitoring_personnel(queryset, user, tab)
        elif user.userlevel == 'Legal Unit':
            queryset = self._filter_legal_unit(queryset, user, tab)
        
        # Additional filters
        if status_filter:
            queryset = queryset.filter(current_status=status_filter)
        if assigned_to_me:
            queryset = queryset.filter(assigned_to=user)
        if created_by_me:
            queryset = queryset.filter(created_by=user)
        
        # Law filter
        law_param = self.request.query_params.get('law')
        if law_param:
            # Support comma-separated laws for multiple selection
            laws = [l.strip() for l in law_param.split(',') if l.strip()]
            if laws:
                queryset = queryset.filter(law__in=laws)
        
        # Establishment filter
        establishment_id = self.request.query_params.get('establishment')
        if establishment_id:
            queryset = queryset.filter(establishments__id=establishment_id)
        
        # Date range filters
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        if date_from:
            try:
                from datetime import datetime
                date_from_obj = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
                queryset = queryset.filter(created_at__gte=date_from_obj)
            except (ValueError, AttributeError):
                pass  # Invalid date format, skip filter
        if date_to:
            try:
                from datetime import datetime
                date_to_obj = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
                # Add one day to include the entire end date
                from datetime import timedelta
                date_to_obj = date_to_obj + timedelta(days=1)
                queryset = queryset.filter(created_at__lt=date_to_obj)
            except (ValueError, AttributeError):
                pass  # Invalid date format, skip filter
        
        # Search functionality
        if search:
            queryset = self._apply_search_filter(queryset, search)
        
        # Sorting
        order_by = self.request.query_params.get('order_by', 'created_at')
        order_direction = self.request.query_params.get('order_direction', 'desc')
        
        # Validate sort field
        valid_sort_fields = ['code', 'created_at', 'updated_at', 'current_status', 'law']
        if order_by in valid_sort_fields:
            # Apply direction
            if order_direction == 'desc':
                order_by = f'-{order_by}'
            queryset = queryset.order_by(order_by)
        else:
            # Default sorting
            queryset = queryset.order_by('-created_at')
        
        return queryset.select_related(
            'created_by', 'assigned_to'
        ).prefetch_related('establishments', 'history').distinct()
    
    def _filter_section_chief(self, queryset, user, tab):
        """Filter for Section Chief based on tab"""
        # Setup law filter for combined EIA section
        law_filter = Q(law=user.section)
        if user.section == 'PD-1586,RA-8749,RA-9275':
            law_filter = Q(law=user.section) | Q(law='PD-1586') | Q(law='RA-8749') | Q(law='RA-9275')
        
        if tab == 'section_assigned':
            # Show inspections assigned to this Section Chief but not yet started
            return queryset.filter(
                law_filter,
                current_status='SECTION_ASSIGNED'
            )
        elif tab == 'section_in_progress':
            # Show inspections that this Section Chief is currently working on
            # Exclude returned inspections (they should only appear in returned_inspection tab)
            from inspections.models import InspectionHistory
            returned_subquery = InspectionHistory.objects.filter(
                inspection=OuterRef('pk'),
                remarks__icontains='Returned'
            )
            return queryset.filter(
                law_filter,
                assigned_to=user,
                current_status__in=[
                    'SECTION_IN_PROGRESS'
                ]
            ).exclude(
                Exists(returned_subquery)
            )
        elif tab == 'forwarded':
            # Show inspections forwarded to Unit Head or Monitoring Personnel (status-based)
            return queryset.filter(
                law_filter,
                current_status__in=[
                    'UNIT_ASSIGNED',
                    'UNIT_IN_PROGRESS',
                    'MONITORING_ASSIGNED',
                    'MONITORING_IN_PROGRESS'
                ]
            )
        elif tab == 'inspection_complete':
            # Only show inspections this Section Chief personally completed
            return queryset.filter(
                law_filter,
                form__inspected_by=user,
                current_status__in=[
                    'SECTION_COMPLETED_COMPLIANT',
                    'SECTION_COMPLETED_NON_COMPLIANT'
                ]
            )
        elif tab == 'review':
            # Show inspections ready for Section Chief review
            return queryset.filter(
                law_filter,
                current_status__in=[
                    'UNIT_COMPLETED_COMPLIANT',
                    'UNIT_COMPLETED_NON_COMPLIANT',
                    'UNIT_REVIEWED'
                ]
            )
        elif tab == 'under_review':
            # Show inspections currently under Division review after Section hand-off
            return queryset.filter(
                law_filter,
                current_status='DIVISION_REVIEWED'
            )
        elif tab == 'compliant':
            # Show only COMPLIANT inspections
            return queryset.filter(
                law_filter,
                form__compliance_decision='COMPLIANT',
                current_status='CLOSED_COMPLIANT'
            )
        elif tab == 'non_compliant':
            # Show only NON_COMPLIANT inspections
            return queryset.filter(
                law_filter,
                form__compliance_decision__in=['NON_COMPLIANT', 'PARTIALLY_COMPLIANT'],
                current_status='CLOSED_NON_COMPLIANT'
            )
        elif tab == 'returned_inspection':
            # Returned items that are back to Section and not yet started
            from inspections.models import InspectionHistory
            # Only show returns directed to Section level
            returned_subquery = InspectionHistory.objects.filter(
                inspection=OuterRef('pk'),
                remarks__icontains='Returned',
                new_status='SECTION_ASSIGNED'
            )
            return queryset.filter(
                law_filter,
                Exists(returned_subquery),
                current_status='SECTION_ASSIGNED'
            ).prefetch_related(
                Prefetch('history',
                    queryset=InspectionHistory.objects.select_related('changed_by', 'assigned_to').order_by('-created_at')
                )
            )
        elif tab == 'returned_reports':
            # Show returned reports that were returned back to Section for rework
            from inspections.models import InspectionHistory
            
            # Use Exists subquery to check for history entries with "Returned" in remarks
            # Only show returns directed to Section level (IN_PROGRESS for active rework, REVIEWED for review stage returns)
            returned_subquery = InspectionHistory.objects.filter(
                inspection=OuterRef('pk'),
                remarks__icontains='Returned',
                new_status__in=['SECTION_IN_PROGRESS', 'SECTION_REVIEWED']
            )
            
            # Filter and prefetch history for serializer
            # Only show items currently in IN_PROGRESS (rework) or REVIEWED (review stage)
            # Also include lower-stage completed statuses (UNIT_COMPLETED, MONITORING_COMPLETED)
            return queryset.filter(
                law_filter,
                current_status__in=['SECTION_IN_PROGRESS', 'SECTION_REVIEWED',
                    'UNIT_COMPLETED_COMPLIANT', 'UNIT_COMPLETED_NON_COMPLIANT',
                    'MONITORING_COMPLETED_COMPLIANT', 'MONITORING_COMPLETED_NON_COMPLIANT']
            ).filter(
                Exists(returned_subquery)
            ).prefetch_related(
                Prefetch('history',
                    queryset=InspectionHistory.objects.select_related('changed_by', 'assigned_to').order_by('-created_at')
                )
            )
        else:
            # Default: show all inspections for this section
            return queryset.filter(law_filter)
    
    def _filter_unit_head(self, queryset, user, tab):
        """Filter for Unit Head based on tab"""
        # Setup law filter for combined EIA section
        law_filter = Q(law=user.section)
        if user.section == 'PD-1586,RA-8749,RA-9275':
            law_filter = Q(law=user.section) | Q(law='PD-1586') | Q(law='RA-8749') | Q(law='RA-9275')
        
        if tab == 'unit_assigned':
            # Show inspections assigned to this Unit Head but not yet started
            return queryset.filter(
                law_filter,
                current_status='UNIT_ASSIGNED'
            )
        elif tab == 'unit_in_progress':
            # Show inspections that this Unit Head is currently working on
            # Exclude returned inspections (they should only appear in returned_inspection tab)
            from inspections.models import InspectionHistory
            returned_subquery = InspectionHistory.objects.filter(
                inspection=OuterRef('pk'),
                remarks__icontains='Returned'
            )
            return queryset.filter(
                law_filter,
                assigned_to=user,
                current_status__in=[
                    'UNIT_IN_PROGRESS'
                ]
            ).exclude(
                Exists(returned_subquery)
            )
        elif tab == 'forwarded':
            # Show inspections forwarded to Monitoring Personnel (status-based)
            return queryset.filter(
                law_filter,
                current_status__in=[
                    'MONITORING_ASSIGNED',
                    'MONITORING_IN_PROGRESS'
                ]
            )
        elif tab == 'inspection_complete':
            # Only show inspections this Unit Head personally completed
            return queryset.filter(
                law_filter,
                form__inspected_by=user,
                current_status__in=[
                    'UNIT_COMPLETED_COMPLIANT',
                    'UNIT_COMPLETED_NON_COMPLIANT'
                ]
            )
        elif tab == 'review':
            # Show inspections ready for Unit Head review
            return queryset.filter(
                law_filter,
                current_status__in=[
                    'MONITORING_COMPLETED_COMPLIANT',
                    'MONITORING_COMPLETED_NON_COMPLIANT'
                ]
            )
        elif tab == 'under_review':
            # Show inspections now being reviewed by Section or Division Chiefs
            return queryset.filter(
                law_filter,
                current_status__in=[
                    'SECTION_REVIEWED',
                    'DIVISION_REVIEWED'
                ]
            )
        elif tab == 'compliant':
            # Show only COMPLIANT inspections
            return queryset.filter(
                law_filter,
                Q(form__inspected_by=user) | 
                Q(form__inspected_by__userlevel='Unit Head', form__inspected_by__section=user.section) | 
                Q(form__inspected_by__userlevel='Monitoring Personnel', form__inspected_by__section=user.section),
                form__compliance_decision='COMPLIANT',
                current_status='CLOSED_COMPLIANT'
            )
        elif tab == 'non_compliant':
            # Show only NON_COMPLIANT inspections
            return queryset.filter(
                law_filter,
                Q(form__inspected_by=user) | 
                Q(form__inspected_by__userlevel='Unit Head', form__inspected_by__section=user.section) | 
                Q(form__inspected_by__userlevel='Monitoring Personnel', form__inspected_by__section=user.section),
                form__compliance_decision__in=['NON_COMPLIANT', 'PARTIALLY_COMPLIANT'],
                current_status='CLOSED_NON_COMPLIANT'
            )
        elif tab == 'returned_inspection':
            # Returned items that are back to Unit and not yet started
            from inspections.models import InspectionHistory
            # Only show returns directed to Unit level
            returned_subquery = InspectionHistory.objects.filter(
                inspection=OuterRef('pk'),
                remarks__icontains='Returned',
                new_status='UNIT_ASSIGNED'
            )
            return queryset.filter(
                law_filter,
                Exists(returned_subquery),
                current_status='UNIT_ASSIGNED'
            ).prefetch_related(
                Prefetch('history',
                    queryset=InspectionHistory.objects.select_related('changed_by', 'assigned_to').order_by('-created_at')
                )
            )
        elif tab == 'returned_reports':
            # Show returned reports that were returned back to Unit for rework
            from inspections.models import InspectionHistory
            
            # Use Exists subquery to check for history entries with "Returned" in remarks
            # Only show returns directed to Unit level (IN_PROGRESS for active rework, REVIEWED for review stage returns)
            returned_subquery = InspectionHistory.objects.filter(
                inspection=OuterRef('pk'),
                remarks__icontains='Returned',
                new_status__in=['UNIT_IN_PROGRESS', 'UNIT_REVIEWED']
            )
            
            # Filter and prefetch history for serializer
            # Only show items currently in IN_PROGRESS (rework) or REVIEWED (review stage)
            return queryset.filter(
                law_filter,
                current_status__in=['UNIT_IN_PROGRESS', 'UNIT_REVIEWED','MONITORING_COMPLETED_COMPLIANT',
                    'MONITORING_COMPLETED_NON_COMPLIANT']
            ).filter(
                Exists(returned_subquery)
            ).prefetch_related(
                Prefetch('history',
                    queryset=InspectionHistory.objects.select_related('changed_by', 'assigned_to').order_by('-created_at')
                )
            )
        else:
            # Default: show all inspections for this section
            return queryset.filter(law_filter)
    
    def _filter_monitoring_personnel(self, queryset, user, tab):
        """Filter for Monitoring Personnel based on tab"""
        if tab == 'assigned':
            # Show inspections assigned to this Monitoring Personnel but not yet started
            return queryset.filter(
                assigned_to=user,
                current_status='MONITORING_ASSIGNED'
            )
        elif tab == 'in_progress':
            # Show inspections that this Monitoring Personnel has started (in progress or with draft)
            # Exclude returned inspections (they should only appear in returned_reports tab)
            from inspections.models import InspectionHistory
            returned_subquery = InspectionHistory.objects.filter(
                inspection=OuterRef('pk'),
                remarks__icontains='Returned'
            )
            return queryset.filter(
                assigned_to=user,
                current_status='MONITORING_IN_PROGRESS'
            ).exclude(
                Exists(returned_subquery)
            )
        elif tab == 'inspection_complete':
            # Only show inspections this Monitoring Personnel personally completed
            return queryset.filter(
                form__inspected_by=user,
                current_status__in=[
                    'MONITORING_COMPLETED_COMPLIANT',
                    'MONITORING_COMPLETED_NON_COMPLIANT'
                ]
            )
        elif tab == 'under_review':
            # Show inspections currently under review after Monitoring completion
            return queryset.filter(
                Q(form__inspected_by=user) | Q(assigned_to=user, form__inspected_by__isnull=True),
                current_status__in=[
                    'UNIT_REVIEWED',
                    'SECTION_REVIEWED', 
                    'DIVISION_REVIEWED'
                ]
            )
        elif tab == 'compliant':
            # Show only COMPLIANT inspections
            return queryset.filter(
                Q(form__inspected_by=user) | Q(assigned_to=user, form__inspected_by__isnull=True),
                form__compliance_decision='COMPLIANT',
                current_status='CLOSED_COMPLIANT'
            )
        elif tab == 'non_compliant':
            # Show only NON_COMPLIANT inspections
            return queryset.filter(
                Q(form__inspected_by=user) | Q(assigned_to=user, form__inspected_by__isnull=True),
                form__compliance_decision__in=['NON_COMPLIANT', 'PARTIALLY_COMPLIANT'],
                current_status='CLOSED_NON_COMPLIANT'
            )
        # No 'returned_inspection' tab for Monitoring Personnel by design
        elif tab == 'returned_reports':
            # Show returned reports that have completed monitoring and were returned back to monitoring for rework
            from inspections.models import InspectionHistory
            
            # Use Exists subquery to check for history entries with "Returned" in remarks
            # Only show returns directed to Monitoring level AND currently in IN_PROGRESS (active rework)
            returned_subquery = InspectionHistory.objects.filter(
                inspection=OuterRef('pk'),
                remarks__icontains='Returned',
                new_status='MONITORING_IN_PROGRESS'
            )
            
            # Filter and prefetch history for serializer
            # Only show items that are currently in IN_PROGRESS (being reworked) AND assigned to this user
            return queryset.filter(
                assigned_to=user,
                current_status='MONITORING_IN_PROGRESS'
            ).filter(
                Exists(returned_subquery)
            ).prefetch_related(
                Prefetch('history',
                    queryset=InspectionHistory.objects.select_related('changed_by', 'assigned_to').order_by('-created_at')
                )
            )
        else:
            # Default: show all assigned inspections
            return queryset.filter(
                assigned_to=user,
                current_status__in=['MONITORING_ASSIGNED', 'MONITORING_IN_PROGRESS', 'MONITORING_COMPLETED_COMPLIANT', 'MONITORING_COMPLETED_NON_COMPLIANT']
            )
    
    def _filter_division_chief(self, queryset, user, tab):
        """Filter for Division Chief based on tab"""
        if tab == 'all_inspections':
            # Show ALL inspections they created - covers entire workflow
            return queryset.filter(created_by=user)
        elif tab == 'review':
            # Show inspections ready for Division Chief review
            review_statuses = [
                'SECTION_REVIEWED',
                    'SECTION_COMPLETED_COMPLIANT',
                'SECTION_COMPLETED_NON_COMPLIANT'
            ]
            return queryset.filter(current_status__in=review_statuses)
        elif tab == 'reviewed':
            # Show inspections already reviewed by the Division Chief
            return queryset.filter(current_status='DIVISION_REVIEWED')
        elif tab == 'compliant':
            # Show only COMPLIANT inspections
            return queryset.filter(
                form__compliance_decision='COMPLIANT',
                current_status='CLOSED_COMPLIANT'
            )
        elif tab == 'non_compliant':
            # Show only NON_COMPLIANT inspections
            return queryset.filter(
                form__compliance_decision__in=['NON_COMPLIANT', 'PARTIALLY_COMPLIANT'],
                current_status='CLOSED_NON_COMPLIANT'
            )
        else:
            # Default to all inspections created by them
            return queryset.filter(created_by=user)

    def _filter_legal_unit(self, queryset, user, tab):
        """Filter for Legal Unit based on tab"""
        if tab == 'legal_review':
            # Show only inspections in legal review status
            return queryset.filter(current_status='LEGAL_REVIEW')
        elif tab == 'nov_sent':
            # Show only inspections with NOV sent
            return queryset.filter(current_status='NOV_SENT')
        elif tab == 'noo_sent':
            # Show only NOO sent inspections
            return queryset.filter(
                current_status='NOO_SENT'
            )
        elif tab == 'compliant':
            # Show only COMPLIANT inspections
            return queryset.filter(
                form__compliance_decision='COMPLIANT',
                current_status='CLOSED_COMPLIANT'
            )
        elif tab == 'non_compliant':
            # Show only NON_COMPLIANT inspections
            return queryset.filter(
                form__compliance_decision__in=['NON_COMPLIANT', 'PARTIALLY_COMPLIANT'],
                current_status='CLOSED_NON_COMPLIANT'
            )
        else:
            # Default: show all legal unit inspections
            return queryset.filter(
                current_status__in=['LEGAL_REVIEW', 'NOV_SENT', 'NOO_SENT', 'CLOSED_NON_COMPLIANT']
            )
    
    def _apply_search_filter(self, queryset, search_term):
        """
        Apply comprehensive search across multiple fields
        Searches: Code, Establishment names, Law, Status, Assigned To
        """
        # Build complex Q query for OR search
        search_query = Q()
        
        # Search in inspection code
        search_query |= Q(code__icontains=search_term)
        
        # Search in law field
        search_query |= Q(law__icontains=search_term)
        
        # Search in current status
        search_query |= Q(current_status__icontains=search_term)
        
        # Search in assigned user's name
        search_query |= Q(assigned_to__first_name__icontains=search_term)
        search_query |= Q(assigned_to__last_name__icontains=search_term)
        search_query |= Q(assigned_to__email__icontains=search_term)
        
        # Search in establishments (name, city, province, nature of business)
        search_query |= Q(establishments__name__icontains=search_term)
        search_query |= Q(establishments__city__icontains=search_term)
        search_query |= Q(establishments__province__icontains=search_term)
        search_query |= Q(establishments__nature_of_business__icontains=search_term)
        
        return queryset.filter(search_query).distinct()
    
    def get_serializer_class(self):
        """Use different serializers for different actions"""
        if self.action == 'create':
            return InspectionCreateSerializer
        return InspectionSerializer
    
    def perform_create(self, serializer):
        """Create inspection (Division Chief only)"""
        if self.request.user.userlevel != 'Division Chief':
            raise permissions.PermissionDenied('Only Division Chiefs can create inspections')
        serializer.save()
    
    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """Get inspection history"""
        inspection = self.get_object()
        history = inspection.history.all()
        serializer = InspectionHistorySerializer(history, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def documents(self, request, pk=None):
        """Upload documents to inspection form"""
        inspection = self.get_object()
        
        # Get or create inspection form
        form, created = InspectionForm.objects.get_or_create(inspection=inspection)
        
        # Handle file upload
        file = request.FILES.get('file')
        document_type = request.data.get('document_type', 'OTHER')
        description = request.data.get('description', '')
        
        if not file:
            return Response(
                {'error': 'No file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create document
        document = InspectionDocument.objects.create(
            inspection_form=form,
            file=file,
            document_type=document_type,
            description=description,
            uploaded_by=request.user
        )
        
        serializer = InspectionDocumentSerializer(document, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'], url_path='findings/documents')
    def findings_documents(self, request, pk=None):
        """Upload finding documents with system association"""
        inspection = self.get_object()
        
        # Get or create inspection form
        form, created = InspectionForm.objects.get_or_create(inspection=inspection)
        
        # Handle file upload
        file = request.FILES.get('file')
        system_id = request.data.get('system_id', 'general')
        caption = request.data.get('caption', '')
        finding_type = request.data.get('finding_type', 'individual')
        
        if not file:
            return Response(
                {'error': 'No file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create document with finding-specific metadata
        document = InspectionDocument.objects.create(
            inspection_form=form,
            file=file,
            document_type='PHOTO',  # Default to PHOTO for finding documents
            description=caption,
            uploaded_by=request.user
        )
        
        # Store additional metadata in the description field
        # Format: "system_id:general|finding_type:general|caption:user_caption"
        metadata = f"system_id:{system_id}|finding_type:{finding_type}|caption:{caption}"
        document.description = metadata
        document.save()
        
        serializer = InspectionDocumentSerializer(document, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['get', 'post', 'delete'], url_path='findings/documents')
    def findings_documents(self, request, pk=None):
        """Get, upload, or delete finding documents with system association"""
        inspection = self.get_object()
        
        if request.method == 'GET':
            # Get finding documents for an inspection
            form, created = InspectionForm.objects.get_or_create(inspection=inspection)
            
            # Get all documents for this inspection form
            documents = form.documents.all()
            
            # Filter by system_id if provided
            system_id = request.query_params.get('system_id')
            if system_id:
                documents = documents.filter(description__contains=f"system_id:{system_id}")
            
            serializer = InspectionDocumentSerializer(documents, many=True, context={'request': request})
            return Response(serializer.data)
        
        elif request.method == 'POST':
            # Upload finding documents with system association
            form, created = InspectionForm.objects.get_or_create(inspection=inspection)
            
            # Handle file upload
            file = request.FILES.get('file')
            system_id = request.data.get('system_id', 'general')
            caption = request.data.get('caption', '')
            finding_type = request.data.get('finding_type', 'individual')
            
            if not file:
                return Response(
                    {'error': 'No file provided'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create document with finding-specific metadata
            document = InspectionDocument.objects.create(
                inspection_form=form,
                file=file,
                document_type='PHOTO',  # Default to PHOTO for finding documents
                description=caption,
                uploaded_by=request.user
            )
            
            # Store additional metadata in the description field
            # Format: "system_id:general|finding_type:general|caption:user_caption"
            metadata = f"system_id:{system_id}|finding_type:{finding_type}|caption:{caption}"
            document.description = metadata
            document.save()
            
            serializer = InspectionDocumentSerializer(document, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        elif request.method == 'DELETE':
            # Delete finding document
            document_id = request.data.get('document_id')
            if not document_id:
                return Response(
                    {'error': 'Document ID is required for deletion'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                # Get or create inspection form
                form, created = InspectionForm.objects.get_or_create(inspection=inspection)
                
                # Find and delete the document
                document = form.documents.filter(id=document_id).first()
                if not document:
                    return Response(
                        {'error': 'Document not found'},
                        status=status.HTTP_404_NOT_FOUND
                    )
                
                # Delete the document
                document.delete()
                
                return Response(
                    {'message': 'Document deleted successfully'},
                    status=status.HTTP_200_OK
                )
                
            except Exception as e:
                return Response(
                    {'error': f'Failed to delete document: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
    
    @action(detail=True, methods=['post'])
    def inspect(self, request, pk=None):
        """Move inspection to My Inspections (Section Chief/Unit Head/Monitoring Personnel)"""
        inspection = self.get_object()
        user = request.user
        
        valid_statuses = ['SECTION_ASSIGNED', 'UNIT_ASSIGNED', 'MONITORING_ASSIGNED']
        if inspection.current_status not in valid_statuses:
            return Response(
                {'error': f'Cannot inspect from status {inspection.current_status}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        status_map = {
            'SECTION_ASSIGNED': 'SECTION_IN_PROGRESS',
            'UNIT_ASSIGNED': 'UNIT_IN_PROGRESS',
            'MONITORING_ASSIGNED': 'MONITORING_IN_PROGRESS',
        }
        next_status = status_map.get(inspection.current_status)

        if not inspection.can_transition_to(next_status, user):
            return Response(
                {'error': f'You are not authorized to transition to {next_status}'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Assign to current user if needed
        reassigned = False
        if inspection.assigned_to != user:
            inspection.assigned_to = user
            reassigned = True

        prev_status = inspection.current_status
        inspection.current_status = next_status
        inspection.save()
        
        # Log history
        default_remarks = 'Moved to My Inspections'
        if reassigned:
            default_remarks = 'Self-assigned and moved to My Inspections'
        remarks = request.data.get('remarks', default_remarks)
        InspectionHistory.objects.create(
            inspection=inspection,
            previous_status=prev_status,
            new_status=inspection.current_status,
            changed_by=user,
            assigned_to=inspection.assigned_to,
            law=inspection.law,
            section=user.section,
            remarks=remarks
        )
        
        audit_inspection_event(
            user,
            inspection,
            AUDIT_ACTIONS["UPDATE"],
            f"{user.email} moved inspection to {inspection.current_status}",
            request,
            metadata={
                "previous_status": prev_status,
                "new_status": inspection.current_status,
                "remarks": remarks,
            },
        )

        serializer = self.get_serializer(inspection)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """Start inspection (Section/Unit/Monitoring)"""
        inspection = self.get_object()
        user = request.user
        
        # If user is not assigned, assign them first
        if inspection.assigned_to != user:
            # Check if user can be assigned (not already assigned to someone else)
            if inspection.assigned_to and inspection.assigned_to != user:
                return Response(
                    {'error': f'Already assigned to {inspection.assigned_to}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            # Assign the user
            inspection.assigned_to = user
        
        # Determine next status
        status_map = {
            'SECTION_ASSIGNED': 'SECTION_IN_PROGRESS',
            'UNIT_ASSIGNED': 'UNIT_IN_PROGRESS',
            'MONITORING_ASSIGNED': 'MONITORING_IN_PROGRESS',
        }
        
        next_status = status_map.get(inspection.current_status)
        if not next_status:
            return Response(
                {'error': f'Cannot start from status {inspection.current_status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if transition is valid
        if not inspection.can_transition_to(next_status, user):
            return Response(
                {'error': f'Invalid transition to {next_status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Transition
        prev_status = inspection.current_status
        inspection.current_status = next_status
        inspection.save()
        
        # Log history
        remarks = request.data.get('remarks', 'Started inspection')
        if inspection.assigned_to == user and prev_status != inspection.current_status:
            remarks = f'Assigned to self and {remarks.lower()}'
        
        InspectionHistory.objects.create(
            inspection=inspection,
            previous_status=prev_status,
            new_status=next_status,
            changed_by=user,
            remarks=remarks
        )
        
        audit_inspection_event(
            user,
            inspection,
            AUDIT_ACTIONS["UPDATE"],
            f"{user.email} started inspection (status {next_status})",
            request,
            metadata={
                "previous_status": prev_status,
                "new_status": next_status,
                "remarks": remarks,
            },
        )

        serializer = self.get_serializer(inspection)
        return Response(serializer.data)
    
    @action(detail=True, methods=["post"])
    def return_to_previous(self, request, pk=None):
        """Return inspection to previous assignment stage."""
        inspection = self.get_object()
        user = request.user

        next_status = None
        next_assignee = None

        if inspection.current_status == "MONITORING_ASSIGNED":
            if user.userlevel not in ["Monitoring Personnel", "Unit Head"]:
                return Response(
                    {"error": "Only Monitoring Personnel or Unit Heads can return monitoring assignments"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            previous_stage = (
                InspectionHistory.objects.filter(
                    inspection=inspection,
                    new_status__in=["UNIT_ASSIGNED", "SECTION_ASSIGNED"],
                )
                .order_by("-created_at")
                .first()
            )

            if previous_stage:
                next_status = previous_stage.new_status
                next_assignee = previous_stage.assigned_to

            if not next_status:
                target = request.data.get("target", "unit")
                next_status = "SECTION_ASSIGNED" if target == "section" else "UNIT_ASSIGNED"
        elif inspection.current_status == "UNIT_ASSIGNED":
            if user.userlevel != "Unit Head":
                return Response(
                    {"error": "Only Unit Heads can return unit assignments"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            previous_stage = (
                InspectionHistory.objects.filter(
                    inspection=inspection,
                    new_status="SECTION_ASSIGNED",
                )
                .order_by("-created_at")
                .first()
            )
            if previous_stage:
                next_status = "SECTION_ASSIGNED"
                next_assignee = previous_stage.assigned_to
            else:
                next_status = "SECTION_ASSIGNED"
        else:
            return Response(
                {"error": f"Return not allowed from status {inspection.current_status}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not inspection.can_transition_to(next_status, user):
            return Response(
                {"error": f"Invalid transition to {next_status}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not next_assignee:
            next_assignee = inspection.get_next_assignee(next_status)

        if not next_assignee and next_status == "UNIT_ASSIGNED":
            # Fallback to Section Chief when no Unit Head is available
            next_status = "SECTION_ASSIGNED"
            next_assignee = inspection.get_next_assignee(next_status)

        if not next_assignee:
            return Response(
                {"error": f"No assignee found for status {next_status}"},
                status=status.HTTP_404_NOT_FOUND,
            )

        prev_status = inspection.current_status
        inspection.current_status = next_status
        inspection.assigned_to = next_assignee
        
        # Clear signatures when returning inspection
        self._clear_signatures_on_return(inspection)
        
        inspection.save()

        remarks = request.data.get("remarks")
        if not remarks:
            status_messages = {
                "UNIT_ASSIGNED": "Returned to Unit Head",
                "SECTION_ASSIGNED": "Returned to Section Chief",
            }
            remarks = status_messages.get(next_status, "Returned to previous stage")
        else:
            # Ensure custom remarks include "Returned" prefix for filtering
            if not remarks.lower().startswith("returned"):
                status_messages = {
                    "UNIT_ASSIGNED": "Returned to Unit Head: ",
                    "SECTION_ASSIGNED": "Returned to Section Chief: ",
                }
                prefix = status_messages.get(next_status, "Returned to previous stage: ")
                remarks = prefix + remarks

        InspectionHistory.objects.create(
            inspection=inspection,
            previous_status=prev_status,
            new_status=next_status,
            changed_by=user,
            assigned_to=inspection.assigned_to,
            law=inspection.law,
            section=user.section,
            remarks=remarks,
        )

        audit_inspection_event(
            user,
            inspection,
            AUDIT_ACTIONS["UPDATE"],
            f"{user.email} returned inspection to {inspection.assigned_to}",
            request,
            metadata={
                "previous_status": prev_status,
                "new_status": next_status,
                "remarks": remarks,
            },
        )

        serializer = self.get_serializer(inspection)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def continue_inspection(self, request, pk=None):
        """Continue inspection (Monitoring Personnel only)"""
        inspection = self.get_object()
        user = request.user
        
        # Check if user can act
        if inspection.assigned_to != user:
            return Response(
                {'error': 'You are not assigned to this inspection'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Only allow for MONITORING_IN_PROGRESS status
        if inspection.current_status != 'MONITORING_IN_PROGRESS':
            return Response(
                {'error': f'Cannot continue from status {inspection.current_status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Log history
        remarks = request.data.get('remarks', 'Continued inspection')
        InspectionHistory.objects.create(
            inspection=inspection,
            previous_status=inspection.current_status,
            new_status=inspection.current_status,
            changed_by=user,
            remarks=remarks
        )
        
        audit_inspection_event(
            user,
            inspection,
            AUDIT_ACTIONS["UPDATE"],
            f"{user.email} continued inspection",
            request,
            metadata={
                "remarks": remarks,
            },
        )

        serializer = self.get_serializer(inspection)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def save_draft(self, request, pk=None):
        """Save inspection form as draft"""
        inspection = self.get_object()
        user = request.user
        
        # Check if user can act
        if inspection.assigned_to != user:
            return Response(
                {'error': 'You are not assigned to this inspection'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get or create inspection form
        form, created = InspectionForm.objects.get_or_create(
            inspection=inspection
        )
        
        # Update form with draft data
        form_data = request.data.get('form_data', {})
        
        # Store all form data in the checklist JSON field
        form.checklist = {
            'general': form_data.get('general', {}),
            'purpose': form_data.get('purpose', {}),
            'permits': form_data.get('permits', []),
            'complianceItems': form_data.get('complianceItems', []),
            'systems': form_data.get('systems', []),
            'recommendationState': form_data.get('recommendationState', {}),
            'lawFilter': form_data.get('lawFilter', []),
            'findingImages': form_data.get('findingImages', {}),
            'generalFindings': form_data.get('generalFindings', []),
            'is_draft': True,
            'last_saved': timezone.now().isoformat(),
            'saved_by': user.id
        }
        
        # Update direct fields from general data
        general_data = form_data.get('general', {})
        if general_data.get('violations_found'):
            form.violations_found = general_data['violations_found']
        if general_data.get('compliance_observations'):
            form.compliance_decision = general_data['compliance_observations']
        
        # Update scheduled_at if provided
        if 'general' in form_data and form_data['general'].get('inspectionDateTime'):
            try:
                form.scheduled_at = form_data['general']['inspectionDateTime']
            except:
                pass
        
        
        # Capture inspector information if this is the first time
        is_first_fill = capture_inspector_info(form, user)
        
        form.save()
        
        # If inspection is in MONITORING_ASSIGNED status, change to MONITORING_IN_PROGRESS when draft is saved
        if inspection.current_status == 'MONITORING_ASSIGNED':
            prev_status = inspection.current_status
            inspection.current_status = 'MONITORING_IN_PROGRESS'
            inspection.save()
            
            # Log status change
            InspectionHistory.objects.create(
                inspection=inspection,
                previous_status=prev_status,
                new_status=inspection.current_status,
                changed_by=user,
                remarks='Status changed to In Progress when draft was saved'
            )
            audit_metadata = {
                "previous_status": prev_status,
                "new_status": inspection.current_status,
                "remarks": "Status changed to In Progress when draft was saved",
                "draft": True,
            }
        else:
            # Log draft save without status change
            InspectionHistory.objects.create(
                inspection=inspection,
                previous_status=inspection.current_status,
                new_status=inspection.current_status,
                changed_by=user,
                remarks='Saved inspection form as draft'
            )
            audit_metadata = {
                "previous_status": inspection.current_status,
                "new_status": inspection.current_status,
                "remarks": "Saved inspection form as draft",
                "draft": True,
            }

        audit_inspection_event(
            user,
            inspection,
            AUDIT_ACTIONS["UPDATE"],
            f"{user.email} saved inspection draft",
            request,
            metadata=audit_metadata,
        )
        
        serializer = self.get_serializer(inspection)
        return Response({
            'message': 'Draft saved successfully',
            'inspection': serializer.data
        })
    
    @action(detail=True, methods=['post'])
    def auto_save(self, request, pk=None):
        """Auto-save inspection form (optimized for frequent saves)"""
        inspection = self.get_object()
        user = request.user
        
        # Check if user can act
        if inspection.assigned_to != user:
            return Response(
                {'error': 'You are not assigned to this inspection'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get or create inspection form
        form, created = InspectionForm.objects.get_or_create(
            inspection=inspection
        )
        
        # Get form data
        form_data = request.data
        
        # Validate form data structure
        required_sections = ['general', 'purpose', 'permits', 'complianceItems', 'systems', 'recommendationState']
        for section in required_sections:
            if section not in form_data:
                return Response(
                    {'error': f'Missing required section: {section}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Store all form data in the checklist JSON field
        form.checklist = {
            'general': form_data.get('general', {}),
            'purpose': form_data.get('purpose', {}),
            'permits': form_data.get('permits', []),
            'complianceItems': form_data.get('complianceItems', []),
            'systems': form_data.get('systems', []),
            'recommendationState': form_data.get('recommendationState', {}),
            'lawFilter': form_data.get('lawFilter', []),
            'findingImages': form_data.get('findingImages', {}),
            'generalFindings': form_data.get('generalFindings', []),
            'is_draft': True,
            'last_saved': timezone.now().isoformat(),
            'saved_by': user.id,
            'auto_save': True  # Mark as auto-save
        }
        
        # Update direct fields from general data
        general_data = form_data.get('general', {})
        if general_data.get('violations_found'):
            form.violations_found = general_data['violations_found']
        if general_data.get('compliance_observations'):
            form.compliance_decision = general_data['compliance_observations']
        
        # Update scheduled_at if provided
        if 'general' in form_data and form_data['general'].get('inspection_date_time'):
            try:
                form.scheduled_at = form_data['general']['inspection_date_time']
            except:
                pass
        
        
        # Capture inspector information if this is the first time
        is_first_fill = capture_inspector_info(form, user)
        
        form.save()
        
        # Only log history for significant changes (not every auto-save)
        # This reduces database writes for frequent auto-saves
        last_history = InspectionHistory.objects.filter(
            inspection=inspection
        ).order_by('-created_at').first()
        
        # Only create history entry if it's been more than 5 minutes since last save
        should_log = True
        if last_history and last_history.remarks == 'Auto-saved inspection form':
            time_diff = timezone.now() - last_history.created_at
            if time_diff.total_seconds() < 300:  # 5 minutes
                should_log = False
        
        if should_log:
            InspectionHistory.objects.create(
                inspection=inspection,
                previous_status=inspection.current_status,
                new_status=inspection.current_status,
                changed_by=user,
                remarks='Auto-saved inspection form'
            )
            audit_inspection_event(
                user,
                inspection,
                AUDIT_ACTIONS["UPDATE"],
                f"{user.email} auto-saved inspection form",
                request,
                metadata={
                    "auto_save": True,
                    "remarks": "Auto-saved inspection form",
                },
            )
        
        return Response({
            'message': 'Auto-save successful',
            'last_saved': form.checklist.get('last_saved'),
            'is_draft': True
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def check_form_data(self, request, pk=None):
        """Check if inspection form has any data"""
        inspection = self.get_object()
        user = request.user
        
        # Check if user can access this inspection
        if inspection.assigned_to != user and inspection.created_by != user:
            return Response(
                {'error': 'You are not authorized to access this inspection'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            form = InspectionForm.objects.get(inspection=inspection)
            checklist = form.checklist or {}
            
            # Check if any form section has meaningful data
            has_data = False
            
            # Check general information
            general = checklist.get('general', {})
            if general:
                # Check for any non-empty fields
                for key, value in general.items():
                    if value and str(value).strip():
                        has_data = True
                        break
            
            # Check purpose
            purpose = checklist.get('purpose', {})
            if purpose:
                for key, value in purpose.items():
                    if value and str(value).strip():
                        has_data = True
                        break
            
            # Check permits
            permits = checklist.get('permits', [])
            if permits:
                for permit in permits:
                    for key, value in permit.items():
                        if value and str(value).strip():
                            has_data = True
                            break
                    if has_data:
                        break
            
            # Check compliance items
            compliance_items = checklist.get('complianceItems', [])
            if compliance_items:
                for item in compliance_items:
                    for key, value in item.items():
                        if value and str(value).strip():
                            has_data = True
                            break
                    if has_data:
                        break
            
            # Check systems
            systems = checklist.get('systems', [])
            if systems:
                for system in systems:
                    for key, value in system.items():
                        if value and str(value).strip():
                            has_data = True
                            break
                    if has_data:
                        break
            
            # Check recommendations
            recommendations = checklist.get('recommendationState', {})
            if recommendations:
                for key, value in recommendations.items():
                    if value and str(value).strip():
                        has_data = True
                        break
            
            return Response({
                'has_form_data': has_data,
                'is_draft': checklist.get('is_draft', False),
                'last_saved': checklist.get('last_saved'),
                'form_exists': True
            })
            
        except InspectionForm.DoesNotExist:
            return Response({
                'has_form_data': False,
                'is_draft': False,
                'last_saved': None,
                'form_exists': False
            })
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Complete inspection"""
        inspection = self.get_object()
        user = request.user
        
        # Check if user can act based on role and status
        can_act = False
        
        # Check if user is assigned to this inspection
        if inspection.assigned_to == user:
            can_act = True
        else:
            # Check if user can act based on role and status
            user_level = user.userlevel
            current_status = inspection.current_status
            
            # Monitoring Personnel can complete MONITORING_IN_PROGRESS inspections
            if user_level == 'Monitoring Personnel' and current_status == 'MONITORING_IN_PROGRESS':
                can_act = True
            # Unit Head can complete UNIT_IN_PROGRESS inspections
            elif user_level == 'Unit Head' and current_status == 'UNIT_IN_PROGRESS':
                can_act = True
            # Section Chief can complete SECTION_IN_PROGRESS inspections
            elif user_level == 'Section Chief' and current_status == 'SECTION_IN_PROGRESS':
                can_act = True
        
        if not can_act:
            return Response(
                {'error': f'You are not authorized to complete this inspection. User: {user.userlevel}, Status: {inspection.current_status}, Assigned to: {inspection.assigned_to}'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Handle form data for all roles
        form_data = request.data.get('form_data', {})
        if form_data:
            # Save form data as part of completion for all roles
            form, created = InspectionForm.objects.get_or_create(inspection=inspection)
            
            # Preserve existing signatures if they exist
            existing_signatures = {}
            if form.checklist and 'signatures' in form.checklist:
                existing_signatures = form.checklist['signatures']
            
            # Store all form data in the checklist JSON field
            form.checklist = {
                'general': form_data.get('general', {}),
                'purpose': form_data.get('purpose', {}),
                'permits': form_data.get('permits', []),
                'complianceItems': form_data.get('complianceItems', []),
                'systems': form_data.get('systems', []),
                'recommendationState': form_data.get('recommendationState', {}),
                'lawFilter': form_data.get('lawFilter', []),
                'findingImages': form_data.get('findingImages', {}),
                'generalFindings': form_data.get('generalFindings', []),
                'signatures': existing_signatures,  # Preserve existing signatures
                'is_draft': False,
                'completed_at': timezone.now().isoformat(),
                'completed_by': user.id
            }
            
            # Update direct fields from general data
            general_data = form_data.get('general', {})
            if general_data.get('findings_summary'):
                form.findings_summary = general_data['findings_summary']
            if general_data.get('violations_found'):
                form.violations_found = general_data['violations_found']
            if general_data.get('compliance_observations'):
                form.compliance_decision = general_data['compliance_observations']
            if general_data.get('recommendations'):
                form.compliance_plan = general_data['recommendations']
            
            # Update scheduled_at if provided
            if 'general' in form_data and form_data['general'].get('inspection_date_time'):
                try:
                    from datetime import datetime
                    form.scheduled_at = datetime.fromisoformat(form_data['general']['inspection_date_time'].replace('Z', '+00:00'))
                except:
                    pass
            
            
            # Capture inspector information if this is the first time
            is_first_fill = capture_inspector_info(form, user)
            
            form.save()

        # Validate other data using serializer
        serializer = InspectionActionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        # Handle violations_found from main payload (convert list to string if needed)
        violations_found = data.get('violations_found', [])
        if isinstance(violations_found, list):
            violations_found_str = ', '.join(violations_found) if violations_found else ''
        else:
            violations_found_str = str(violations_found) if violations_found else ''
        
        # Determine compliance decision from request data
        compliance_decision = data.get('compliance_decision', 'COMPLIANT')
        
        # Always update form with compliance_decision - this is critical for all completion scenarios
        form, created = InspectionForm.objects.get_or_create(inspection=inspection)
        form.compliance_decision = compliance_decision
        
        # Update violations_found if form_data exists
        if form_data:
            if not form.violations_found:
                form.violations_found = violations_found_str if violations_found_str else 'None'
        
        form.save()
        
        if inspection.current_status == 'SECTION_IN_PROGRESS':
            # Section Chief completes inspection
            next_status = 'SECTION_COMPLETED_COMPLIANT' if compliance_decision == 'COMPLIANT' else 'SECTION_COMPLETED_NON_COMPLIANT'
        elif inspection.current_status == 'UNIT_IN_PROGRESS':
            # Unit Head completes inspection
            next_status = 'UNIT_COMPLETED_COMPLIANT' if compliance_decision == 'COMPLIANT' else 'UNIT_COMPLETED_NON_COMPLIANT'
        elif inspection.current_status == 'MONITORING_IN_PROGRESS':
            # Monitoring Personnel completes inspection
            next_status = 'MONITORING_COMPLETED_COMPLIANT' if compliance_decision == 'COMPLIANT' else 'MONITORING_COMPLETED_NON_COMPLIANT'
        else:
            return Response(
                {'error': f'Cannot complete from status {inspection.current_status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if transition is valid
        if not inspection.can_transition_to(next_status, user):
            return Response(
                {'error': f'Invalid transition to {next_status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Transition
        prev_status = inspection.current_status
        inspection.current_status = next_status
        inspection.save()
        
        # Log history
        remarks = data.get('remarks', 'Completed inspection')
        InspectionHistory.objects.create(
            inspection=inspection,
            previous_status=prev_status,
            new_status=next_status,
            changed_by=user,
            assigned_to=inspection.assigned_to,
            law=inspection.law,
            section=user.section,
            remarks=remarks
        )
        
        # Audit trail for completion
        audit_inspection_event(
            user,
            inspection,
            AUDIT_ACTIONS["UPDATE"],
            f"{user.email} completed inspection {inspection.code} as {compliance_decision}",
            request,
            metadata={
                "action": "complete",
                "previous_status": prev_status,
                "new_status": next_status,
                "compliance_decision": compliance_decision,
                "violations_found": violations_found_str,
                "remarks": remarks,
            },
        )
        
        # Send notifications based on completion status
        try:
            # Determine if this is a non-compliant path
            is_non_compliant = 'NON_COMPLIANT' in next_status
            
            # Get next assignee based on completion status
            next_assignee = None
            if next_status in ['MONITORING_COMPLETED_COMPLIANT', 'MONITORING_COMPLETED_NON_COMPLIANT']:
                next_assignee = inspection.get_next_assignee('UNIT_REVIEWED')
            elif next_status in ['UNIT_COMPLETED_COMPLIANT', 'UNIT_COMPLETED_NON_COMPLIANT']:
                next_assignee = inspection.get_next_assignee('SECTION_REVIEWED')
            elif next_status in ['SECTION_COMPLETED_COMPLIANT', 'SECTION_COMPLETED_NON_COMPLIANT']:
                next_assignee = inspection.get_next_assignee('DIVISION_REVIEWED')
            
            if next_assignee:
                # For non-compliant: send email + system notification
                if is_non_compliant:
                    from .utils import send_inspection_completion_notification
                    send_inspection_completion_notification(inspection, user, next_assignee, next_status)
                
                # For all: create system notification
                from .utils import create_completion_notification
                create_completion_notification(next_assignee, inspection, user, next_status, data.get('remarks'))
                
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send completion notifications for {inspection.code}: {str(e)}")
            # Don't fail the completion if notifications fail
        
        # Auto-assign completed inspections to appropriate reviewers
        if next_status in ['SECTION_COMPLETED_COMPLIANT', 'SECTION_COMPLETED_NON_COMPLIANT']:
            self._auto_assign_to_division_chief(inspection, user)
        elif next_status in ['UNIT_COMPLETED_COMPLIANT', 'UNIT_COMPLETED_NON_COMPLIANT']:
            self._auto_assign_to_section_chief(inspection, user)
        elif next_status in ['MONITORING_COMPLETED_COMPLIANT', 'MONITORING_COMPLETED_NON_COMPLIANT']:
            self._auto_assign_to_unit_head(inspection, user)
        
        serializer = self.get_serializer(inspection)
        return Response(serializer.data)
    
    def _auto_forward_to_unit_review(self, inspection, user):
        """Auto-forward monitoring completed to Unit Head review"""
        prev_status = inspection.current_status
        inspection.current_status = 'UNIT_REVIEWED'
        
        # Find Unit Head
        next_assignee = inspection.get_next_assignee('UNIT_REVIEWED')
        if next_assignee:
            inspection.assigned_to = next_assignee
        
        inspection.save()
        
        # Log history
        InspectionHistory.objects.create(
            inspection=inspection,
            previous_status=prev_status,
            new_status='UNIT_REVIEWED',
            changed_by=user,
            remarks='Auto-forwarded to Unit Head for review'
        )
    
    def _auto_forward_to_division_review(self, inspection, user):
        """Auto-forward section completed to Division Chief review"""
        prev_status = inspection.current_status
        inspection.current_status = 'DIVISION_REVIEWED'
        
        # Find Division Chief (creator of the inspection)
        if inspection.created_by:
            inspection.assigned_to = inspection.created_by
        else:
            # Fallback: find any Division Chief
            from users.models import User
            division_chief = User.objects.filter(userlevel='Division Chief').first()
            if division_chief:
                inspection.assigned_to = division_chief
        
        inspection.save()
        
        # Log history
        InspectionHistory.objects.create(
            inspection=inspection,
            previous_status=prev_status,
            new_status='DIVISION_REVIEWED',
            changed_by=user,
            remarks='Auto-forwarded to Division Chief for review'
        )
    
    def _auto_forward_to_section_review(self, inspection, user):
        """Auto-forward unit completed to Section Chief review"""
        prev_status = inspection.current_status
        inspection.current_status = 'SECTION_REVIEWED'
        
        # Find Section Chief (original assignee or based on law)
        from users.models import User
        # Special case: PD-1586, RA-8749, RA-9275 should use combined section
        target_section = inspection.law
        if inspection.law in ['PD-1586', 'RA-8749', 'RA-9275']:
            target_section = 'PD-1586,RA-8749,RA-9275'  # EIA, Air & Water Combined
        
        section_chief = User.objects.filter(
            userlevel='Section Chief',
            section=target_section
        ).first()
        
        if section_chief:
            inspection.assigned_to = section_chief
        else:
            # Fallback: find any Section Chief
            section_chief = User.objects.filter(userlevel='Section Chief').first()
            if section_chief:
                inspection.assigned_to = section_chief
        
        inspection.save()
        
        # Log history
        InspectionHistory.objects.create(
            inspection=inspection,
            previous_status=prev_status,
            new_status='SECTION_REVIEWED',
            changed_by=user,
            remarks='Auto-forwarded to Section Chief for review'
        )
    
    def _auto_assign_to_section_chief(self, inspection, user):
        """Auto-assign to Section Chief for review (status unchanged)"""
        # Find Section Chief based on law
        target_section = inspection.law
        if inspection.law in ['PD-1586', 'RA-8749', 'RA-9275']:
            target_section = 'PD-1586,RA-8749,RA-9275'
        
        section_chief = User.objects.filter(
            userlevel='Section Chief',
            section=target_section,
            is_active=True
        ).first()
        
        if section_chief:
            inspection.assigned_to = section_chief
            inspection.save()
            
            InspectionHistory.objects.create(
                inspection=inspection,
                previous_status=inspection.current_status,
                new_status=inspection.current_status,
                changed_by=user,
                assigned_to=inspection.assigned_to,
                law=inspection.law,
                section=user.section,
                remarks=f'Assigned to Section Chief for review'
            )
    
    def _auto_assign_to_division_chief(self, inspection, user):
        """Auto-assign to Division Chief for review (status unchanged)"""
        # Find Division Chief (creator of the inspection)
        if inspection.created_by:
            inspection.assigned_to = inspection.created_by
        else:
            # Fallback: find any Division Chief
            division_chief = User.objects.filter(userlevel='Division Chief', is_active=True).first()
            if division_chief:
                inspection.assigned_to = division_chief
        
        if inspection.assigned_to:
            inspection.save()
            
            InspectionHistory.objects.create(
                inspection=inspection,
                previous_status=inspection.current_status,
                new_status=inspection.current_status,
                changed_by=user,
                remarks=f'Assigned to Division Chief for review'
            )
    
    def _auto_assign_to_unit_head(self, inspection, user):
        """Auto-assign to Unit Head (combined section) or Section Chief (individual section) for review"""
        # Check if this is a combined section inspection
        is_combined_section = inspection.law in ['PD-1586', 'RA-8749', 'RA-9275']
        
        if is_combined_section:
            # Combined section: Assign to Unit Head
            unit_head = User.objects.filter(
                userlevel='Unit Head',
                section=inspection.law,
                is_active=True
            ).first()
            
            if unit_head:
                inspection.assigned_to = unit_head
                inspection.save()
                
                InspectionHistory.objects.create(
                    inspection=inspection,
                    previous_status=inspection.current_status,
                    new_status=inspection.current_status,
                    changed_by=user,
                    remarks=f'Assigned to Unit Head for review'
                )
        else:
            # Individual section: NO Unit Head, assign to Section Chief
            section_chief = User.objects.filter(
                userlevel='Section Chief',
                section=inspection.law,
                is_active=True
            ).first()
            
            if section_chief:
                inspection.assigned_to = section_chief
                inspection.save()
                
                InspectionHistory.objects.create(
                    inspection=inspection,
                    previous_status=inspection.current_status,
                    new_status=inspection.current_status,
                    changed_by=user,
                    remarks=f'Assigned to Section Chief for review (no Unit Head in workflow)'
                )
    
    def _last_history_entry(self, inspection, statuses, *, require_assignee=False):
        """
        Return the most recent history entry for the provided statuses.
        """
        history_qs = inspection.history.filter(new_status__in=statuses).order_by('-created_at')
        if require_assignee:
            history_qs = history_qs.filter(assigned_to__isnull=False)
        return history_qs.first()

    def _get_stage_assignee(self, inspection, stage_statuses, default_status, expected_userlevel=None):
        """
        Determine the most recent assignee for a workflow stage, preferring users with the expected role.
        """
        history_entries = inspection.history.filter(
            new_status__in=stage_statuses,
            assigned_to__isnull=False,
        ).select_related('assigned_to').order_by('-created_at')

        if expected_userlevel:
            for entry in history_entries:
                assigned_user = entry.assigned_to
                if assigned_user and getattr(assigned_user, 'userlevel', None) == expected_userlevel:
                    return assigned_user

        entry = history_entries.first()
        if entry and entry.assigned_to:
            return entry.assigned_to

        if default_status:
            return inspection.get_next_assignee(default_status)
        return None

    def _clear_signatures_on_return(self, inspection):
        """
        Clear all signatures when an inspection is returned.
        Also deletes the signature files from storage.
        """
        from django.core.files.storage import default_storage
        
        form = getattr(inspection, 'form', None)
        if not form:
            return
        
        checklist = form.checklist or {}
        signatures = checklist.get('signatures', {})
        
        if not signatures:
            return
        
        # Delete signature files from storage
        for slot, signature_data in signatures.items():
            url = signature_data.get('url', '')
            if url:
                try:
                    # Extract path from URL (similar to delete_signature method)
                    # Handle both absolute URLs and relative paths
                    if url.startswith('http://') or url.startswith('https://'):
                        # Extract path from absolute URL
                        if '/media/' in url:
                            path = url.split('/media/')[1]
                        else:
                            # Try using base_url replacement
                            path = url.replace(default_storage.base_url, '')
                    else:
                        # Already a relative path
                        path = url.replace(default_storage.base_url, '')
                    
                    # Delete file if it exists
                    if path and default_storage.exists(path):
                        default_storage.delete(path)
                except Exception as exc:
                    # Log error but don't fail the return operation
                    logger.warning(
                        f"Failed to delete signature file {url} for inspection {inspection.code}: {exc}"
                    )
        
        # Clear signatures from checklist
        checklist['signatures'] = {}
        form.checklist = checklist
        form.save(update_fields=['checklist'])

    def _execute_return_transition(
        self,
        *,
        inspection,
        user,
        target_status,
        assignee,
        remarks,
        request,
        return_label,
        extra_metadata=None,
    ):
        """
        Apply the return transition, log history, send notifications, and audit.
        """
        if not assignee:
            return Response(
                {'error': f'No assignee found for status {target_status}'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Clear signatures when returning inspection
        self._clear_signatures_on_return(inspection)

        prev_status = inspection.current_status
        inspection.current_status = target_status
        inspection.assigned_to = assignee
        inspection.save()

        history_remarks = f"{return_label}: {remarks}" if return_label else remarks
        InspectionHistory.objects.create(
            inspection=inspection,
            previous_status=prev_status,
            new_status=target_status,
            changed_by=user,
            assigned_to=assignee,
            law=inspection.law,
            section=getattr(assignee, 'section', getattr(user, 'section', None)),
            remarks=history_remarks,
        )

        try:
            create_return_notification(
                assignee,
                inspection,
                user,
                target_status,
                remarks,
            )
        except Exception as exc:  # pragma: no cover - notification failure should not block flow
            logger.error(
                "Failed to send return notification for %s: %s",
                inspection.code,
                exc,
            )

        metadata = {
            "previous_status": prev_status,
            "return_status": target_status,
            "remarks": remarks,
            "reassigned_to": getattr(assignee, "email", None),
        }
        if extra_metadata:
            metadata.update(extra_metadata)

        audit_inspection_event(
            user,
            inspection,
            AUDIT_ACTIONS["UPDATE"],
            f"{user.email} returned inspection to {assignee.email}",
            request,
            metadata=metadata,
        )

        serializer = self.get_serializer(inspection)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def return_to_monitoring(self, request, pk=None):
        """Unit Head returns inspection to Monitoring stage with remarks."""
        inspection = self.get_object()
        user = request.user

        if user.userlevel != 'Unit Head':
            return Response(
                {'error': 'Only Unit Heads can return inspections to the monitoring stage.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        monitoring_completed_statuses = ['MONITORING_COMPLETED_COMPLIANT', 'MONITORING_COMPLETED_NON_COMPLIANT']
        if inspection.current_status not in monitoring_completed_statuses:
            return Response(
                {'error': f'Cannot return to monitoring from status {inspection.current_status}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        remarks = (request.data.get('remarks') or '').strip()
        if not remarks:
            return Response(
                {'error': 'Remarks are required when returning an inspection.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        monitoring_stage_statuses = [
            'MONITORING_COMPLETED_COMPLIANT',
            'MONITORING_COMPLETED_NON_COMPLIANT',
            'MONITORING_IN_PROGRESS',
            'MONITORING_ASSIGNED',
        ]
        assignee = self._get_stage_assignee(
            inspection,
            monitoring_stage_statuses,
            'MONITORING_IN_PROGRESS',
            expected_userlevel='Monitoring Personnel',
        )

        metadata = {
            'original_stage_status': inspection.current_status,
            'restored_stage_status': 'MONITORING_IN_PROGRESS',
        }

        return self._execute_return_transition(
            inspection=inspection,
            user=user,
            target_status='MONITORING_IN_PROGRESS',
            assignee=assignee,
            remarks=remarks,
            request=request,
            return_label='Returned to Monitoring Personnel',
            extra_metadata=metadata,
        )

    @action(detail=True, methods=['post'])
    def return_to_unit(self, request, pk=None):
        """Section Chief returns inspection to Unit (or Monitoring when Unit stage absent)."""
        inspection = self.get_object()
        user = request.user

        if user.userlevel != 'Section Chief':
            return Response(
                {'error': 'Only Section Chiefs can return inspections to the unit stage.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        valid_statuses = [
            'UNIT_REVIEWED',
            'UNIT_COMPLETED_COMPLIANT',
            'UNIT_COMPLETED_NON_COMPLIANT',
            'MONITORING_COMPLETED_COMPLIANT',
            'MONITORING_COMPLETED_NON_COMPLIANT',
        ]
        if inspection.current_status not in valid_statuses:
            return Response(
                {'error': f'Cannot return to unit from status {inspection.current_status}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        remarks = (request.data.get('remarks') or '').strip()
        if not remarks:
            return Response(
                {'error': 'Remarks are required when returning an inspection.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        monitoring_completed_statuses = ['MONITORING_COMPLETED_COMPLIANT', 'MONITORING_COMPLETED_NON_COMPLIANT']
        unit_completed_statuses = ['UNIT_COMPLETED_COMPLIANT', 'UNIT_COMPLETED_NON_COMPLIANT']
        unit_stage_statuses = unit_completed_statuses + ['UNIT_IN_PROGRESS', 'UNIT_ASSIGNED']
        monitoring_stage_statuses = monitoring_completed_statuses + ['MONITORING_IN_PROGRESS', 'MONITORING_ASSIGNED']

        metadata = {
            'original_stage_status': inspection.current_status,
        }

        if inspection.current_status == 'UNIT_REVIEWED':
            monitoring_entry = self._last_history_entry(inspection, monitoring_completed_statuses)
            if not monitoring_entry:
                return Response(
                    {'error': 'Unable to locate previous monitoring completion status for this inspection.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            target_status = monitoring_entry.new_status
            assignee = self._get_stage_assignee(
                inspection,
                monitoring_stage_statuses,
                'MONITORING_IN_PROGRESS',
                expected_userlevel='Monitoring Personnel',
            )
            metadata['restored_stage_status'] = target_status
            return self._execute_return_transition(
                inspection=inspection,
                user=user,
                target_status=target_status,
                assignee=assignee,
                remarks=remarks,
                request=request,
                return_label='Returned to Monitoring Personnel',
                extra_metadata=metadata,
            )

        if inspection.current_status in unit_completed_statuses:
            assignee = self._get_stage_assignee(
                inspection,
                unit_stage_statuses,
                'UNIT_IN_PROGRESS',
                expected_userlevel='Unit Head',
            )
            metadata['restored_stage_status'] = 'UNIT_IN_PROGRESS'
            return self._execute_return_transition(
                inspection=inspection,
                user=user,
                target_status='UNIT_IN_PROGRESS',
                assignee=assignee,
                remarks=remarks,
                request=request,
                return_label='Returned to Unit Head',
                extra_metadata=metadata,
            )

        # Monitoring completed with no unit stage
        unit_history_exists = inspection.history.filter(new_status__in=unit_stage_statuses + ['UNIT_REVIEWED']).exists()
        if unit_history_exists:
            return Response(
                {'error': 'This inspection already passed through the unit stage and cannot return directly to monitoring as a no-unit workflow.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        assignee = self._get_stage_assignee(
            inspection,
            monitoring_stage_statuses,
            'MONITORING_IN_PROGRESS',
            expected_userlevel='Monitoring Personnel',
        )
        metadata['restored_stage_status'] = 'MONITORING_IN_PROGRESS'
        return self._execute_return_transition(
            inspection=inspection,
            user=user,
            target_status='MONITORING_IN_PROGRESS',
            assignee=assignee,
            remarks=remarks,
            request=request,
            return_label='Returned to Monitoring Personnel',
            extra_metadata=metadata,
        )

    @action(detail=True, methods=['post'])
    def return_to_section(self, request, pk=None):
        """Division Chief returns inspection to Section stage with remarks."""
        inspection = self.get_object()
        user = request.user

        if user.userlevel not in ['Division Chief']:
            return Response(
                {'error': 'Only Division Chiefs can return inspections to the section stage.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        valid_statuses = [
            'SECTION_REVIEWED',
            'SECTION_COMPLETED_COMPLIANT',
            'SECTION_COMPLETED_NON_COMPLIANT',
            'DIVISION_REVIEWED',  # Division Chief can return from review status
        ]
        if inspection.current_status not in valid_statuses:
            return Response(
                {'error': f'Cannot return to section from status {inspection.current_status}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        remarks = (request.data.get('remarks') or '').strip()
        if not remarks:
            return Response(
                {'error': 'Remarks are required when returning an inspection.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        unit_completed_statuses = ['UNIT_COMPLETED_COMPLIANT', 'UNIT_COMPLETED_NON_COMPLIANT']
        monitoring_completed_statuses = ['MONITORING_COMPLETED_COMPLIANT', 'MONITORING_COMPLETED_NON_COMPLIANT']
        unit_stage_statuses = unit_completed_statuses + ['UNIT_IN_PROGRESS', 'UNIT_ASSIGNED']
        monitoring_stage_statuses = monitoring_completed_statuses + ['MONITORING_IN_PROGRESS', 'MONITORING_ASSIGNED']
        section_stage_statuses = [
            'SECTION_IN_PROGRESS',
            'SECTION_ASSIGNED',
            'SECTION_COMPLETED_COMPLIANT',
            'SECTION_COMPLETED_NON_COMPLIANT',
        ]

        metadata = {
            'original_stage_status': inspection.current_status,
        }

        # Handle DIVISION_REVIEWED status - return to Section Chief who forwarded it
        if inspection.current_status == 'DIVISION_REVIEWED':
            # Find the last Section Chief who reviewed/forwarded this inspection
            section_reviewed_entry = self._last_history_entry(
                inspection, 
                ['SECTION_REVIEWED', 'SECTION_COMPLETED_COMPLIANT', 'SECTION_COMPLETED_NON_COMPLIANT']
            )
            
            assignee = None
            if section_reviewed_entry:
                # Try to get assignee from history entry
                if section_reviewed_entry.assigned_to and section_reviewed_entry.assigned_to.userlevel == 'Section Chief':
                    assignee = section_reviewed_entry.assigned_to
                elif section_reviewed_entry.changed_by and section_reviewed_entry.changed_by.userlevel == 'Section Chief':
                    # Use changed_by as fallback (Section Chief who reviewed it)
                    assignee = section_reviewed_entry.changed_by
            
            # If no Section Chief found from history, use default Section Chief assignment
            if not assignee:
                assignee = self._get_stage_assignee(
                    inspection,
                    section_stage_statuses,
                    'SECTION_IN_PROGRESS',
                    expected_userlevel='Section Chief',
                )
            
            target_status = 'SECTION_IN_PROGRESS'
            metadata['restored_stage_status'] = target_status
            return self._execute_return_transition(
                inspection=inspection,
                user=user,
                target_status=target_status,
                assignee=assignee,
                remarks=remarks,
                request=request,
                return_label='Returned to Section Chief',
                extra_metadata=metadata,
            )

        # Handle SECTION_REVIEWED - return to UNIT_REVIEWED or UNIT_COMPLETED_* if unit exists, otherwise MONITORING_COMPLETED_*
        if inspection.current_status == 'SECTION_REVIEWED':
            # Check for unit stage (UNIT_REVIEWED or UNIT_COMPLETED_*)
            unit_reviewed_entry = self._last_history_entry(inspection, ['UNIT_REVIEWED'])
            unit_completed_entry = self._last_history_entry(inspection, unit_completed_statuses)
            
            if unit_reviewed_entry or unit_completed_entry:
                # Unit stage exists - return to unit
                if unit_reviewed_entry:
                    target_status = 'UNIT_REVIEWED'
                    # Include UNIT_REVIEWED in stage statuses when looking for assignee
                    unit_stage_statuses_with_reviewed = unit_stage_statuses + ['UNIT_REVIEWED']
                else:
                    target_status = unit_completed_entry.new_status
                    unit_stage_statuses_with_reviewed = unit_stage_statuses
                
                assignee = self._get_stage_assignee(
                    inspection,
                    unit_stage_statuses_with_reviewed,
                    'UNIT_IN_PROGRESS',
                    expected_userlevel='Unit Head',
                )
                metadata['restored_stage_status'] = target_status
                return_label = 'Returned to Unit Head'
            else:
                # No unit stage - return to monitoring
                monitoring_entry = self._last_history_entry(inspection, monitoring_completed_statuses)
                if not monitoring_entry:
                    return Response(
                        {'error': 'Unable to determine previous workflow stage for this inspection.'},
                        status=status.HTTP_404_NOT_FOUND,
                    )
                target_status = monitoring_entry.new_status
                assignee = self._get_stage_assignee(
                    inspection,
                    monitoring_stage_statuses,
                    'MONITORING_IN_PROGRESS',
                    expected_userlevel='Monitoring Personnel',
                )
                metadata['restored_stage_status'] = target_status
                return_label = 'Returned to Monitoring Personnel'

            return self._execute_return_transition(
                inspection=inspection,
                user=user,
                target_status=target_status,
                assignee=assignee,
                remarks=remarks,
                request=request,
                return_label=return_label,
                extra_metadata=metadata,
            )

        # Handle SECTION_COMPLETED_* - return to SECTION_IN_PROGRESS
        if inspection.current_status in ['SECTION_COMPLETED_COMPLIANT', 'SECTION_COMPLETED_NON_COMPLIANT']:
            assignee = self._get_stage_assignee(
                inspection,
                section_stage_statuses,
                'SECTION_IN_PROGRESS',
                expected_userlevel='Section Chief',
            )
            metadata['restored_stage_status'] = 'SECTION_IN_PROGRESS'
            return self._execute_return_transition(
                inspection=inspection,
                user=user,
                target_status='SECTION_IN_PROGRESS',
                assignee=assignee,
                remarks=remarks,
                request=request,
                return_label='Returned to Section Chief',
                extra_metadata=metadata,
            )

        # Fallback (should not reach here for valid statuses)
        assignee = self._get_stage_assignee(
            inspection,
            section_stage_statuses,
            'SECTION_IN_PROGRESS',
            expected_userlevel='Section Chief',
        )
        metadata['restored_stage_status'] = 'SECTION_IN_PROGRESS'
        return self._execute_return_transition(
            inspection=inspection,
            user=user,
            target_status='SECTION_IN_PROGRESS',
            assignee=assignee,
            remarks=remarks,
            request=request,
            return_label='Returned to Section Chief',
            extra_metadata=metadata,
        )

    @action(detail=True, methods=['get'])
    def available_monitoring_personnel(self, request, pk=None):
        """Get available monitoring personnel for an inspection"""
        inspection = self.get_object()
        
        # Get all monitoring personnel for the inspection's law
        ordering = ['first_name', 'last_name']
        if USER_HAS_DISTRICT:
            ordering = ['district'] + ordering
        
        monitoring_personnel = User.objects.filter(
            userlevel='Monitoring Personnel',
            section=inspection.law,
            is_active=True
        ).order_by(*ordering)
        
        # Separate district-based and other personnel
        district_personnel = []
        other_personnel = []
        
        for person in monitoring_personnel:
            district_value = getattr(person, 'district', None) if USER_HAS_DISTRICT else None
            person_data = {
                'id': person.id,
                'first_name': person.first_name,
                'last_name': person.last_name,
                'email': person.email,
                'district': district_value,
                'is_district_match': USER_HAS_DISTRICT and inspection.district and district_value == inspection.district
            }
            
            if USER_HAS_DISTRICT and inspection.district and district_value == inspection.district:
                district_personnel.append(person_data)
            else:
                other_personnel.append(person_data)
        
        return Response({
            'district_personnel': district_personnel,
            'other_personnel': other_personnel,
            'inspection_district': inspection.district,
            'inspection_law': inspection.law
        })

    @action(detail=True, methods=['post'])
    def forward(self, request, pk=None):
        """Forward inspection to next level"""
        inspection = self.get_object()
        user = request.user
        
        # Determine next status
        status_map = {
            'SECTION_COMPLETED': 'UNIT_ASSIGNED',
            'UNIT_COMPLETED': 'MONITORING_ASSIGNED',
        }
        
        # Section Chief can forward directly to Unit or Monitoring
        if inspection.current_status == 'SECTION_ASSIGNED':
            # Check if unit head exists for this law
            # Special logic based on user's section:
            # - If user is in combined section: look for Unit Head by specific law
            # - If user is in individual section: go directly to Monitoring Personnel
            if user.section == 'PD-1586,RA-8749,RA-9275':
                # Combined section: look for Unit Head by specific law first, then by combined section
                unit_head = User.objects.filter(
                    userlevel='Unit Head',
                    section=inspection.law,  # Try specific law first
                    is_active=True
                ).first()
                
                # If no Unit Head found for specific law, try combined section
                if not unit_head:
                    unit_head = User.objects.filter(
                        userlevel='Unit Head',
                        section='PD-1586,RA-8749,RA-9275',  # Try combined section
                        is_active=True
                    ).first()
                
                if unit_head:
                    next_status = 'UNIT_ASSIGNED'
                else:
                    # No Unit Head found - return error with more helpful message
                    return Response(
                        {'error': f'No Unit Head assigned for {inspection.law} or combined section. Please assign a Unit Head before forwarding.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                # Individual section: go directly to Monitoring Personnel
                next_status = 'MONITORING_ASSIGNED'
        # Unit Head can forward directly to Monitoring Personnel
        elif inspection.current_status == 'UNIT_ASSIGNED':
            next_status = 'MONITORING_ASSIGNED'
        else:
            next_status = status_map.get(inspection.current_status)
        
        if not next_status:
            return Response(
                {'error': f'Cannot forward from status {inspection.current_status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if transition is valid
        if not inspection.can_transition_to(next_status, user):
            return Response(
                {'error': f'Invalid transition to {next_status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get next assignee
        if next_status == 'UNIT_ASSIGNED' and user.section == 'PD-1586,RA-8749,RA-9275':
            # Special case: For combined section forwarding to Unit Head, try specific law first, then combined section
            next_assignee = User.objects.filter(
                userlevel='Unit Head',
                section=inspection.law,  # Try specific law first
                is_active=True
            ).first()
            
            # If no Unit Head found for specific law, try combined section
            if not next_assignee:
                next_assignee = User.objects.filter(
                    userlevel='Unit Head',
                    section='PD-1586,RA-8749,RA-9275',  # Try combined section
                    is_active=True
                ).first()
        elif next_status == 'MONITORING_ASSIGNED':
            # Special case: For Monitoring Personnel, use specific law and prefer same district
            monitoring_query = User.objects.filter(
                userlevel='Monitoring Personnel',
                section=inspection.law,  # Use the specific law
                is_active=True
            )
            
            # Check if specific monitoring personnel is provided in request
            assigned_monitoring_id = request.data.get('assigned_monitoring_id')
            if assigned_monitoring_id:
                try:
                    next_assignee = monitoring_query.get(id=assigned_monitoring_id)
                except User.DoesNotExist:
                    return Response(
                        {'error': f'Invalid monitoring personnel ID: {assigned_monitoring_id}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                # Auto-assignment: Prefer same district if available
                if USER_HAS_DISTRICT and inspection.district:
                    next_assignee = monitoring_query.filter(district=inspection.district).first()
                    if not next_assignee:
                        # No district match - return available options instead of error
                        value_fields = ['id', 'first_name', 'last_name', 'email']
                        if USER_HAS_DISTRICT:
                            value_fields.append('district')
                        available_personnel = monitoring_query.values(*value_fields)
                        return Response(
                            {
                                'error': f'No Monitoring Personnel found for {inspection.law} in district {inspection.district}.',
                                'available_personnel': list(available_personnel),
                                'requires_selection': True
                            },
                            status=status.HTTP_400_BAD_REQUEST
                        )
                else:
                    next_assignee = monitoring_query.first()
                    if not next_assignee:
                        # No Monitoring Personnel found - return error
                        error_message = f'No Monitoring Personnel found for {inspection.law}. Please assign Monitoring Personnel before forwarding.'
                        return Response(
                            {'error': error_message},
                            status=status.HTTP_400_BAD_REQUEST
                        )
        else:
            # Use normal assignment logic
            next_assignee = inspection.get_next_assignee(next_status)
        
        if not next_assignee:
            # This should not happen for MONITORING_ASSIGNED as we handle it above
            # Only for other statuses
            error_msg = f'No personnel found for {next_status}'
            
            return Response(
                {'error': error_msg},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Transition
        prev_status = inspection.current_status
        inspection.current_status = next_status
        inspection.assigned_to = next_assignee
        inspection.save()
        
        # Get remarks before logging history (needed for both notifications and history)
        full_name_parts = [next_assignee.first_name, next_assignee.middle_name, next_assignee.last_name]
        full_name = ' '.join([part for part in full_name_parts if part]).strip()
        display_name = full_name if full_name else next_assignee.email
        default_remarks = f'Forwarded to {display_name} ({next_assignee.userlevel})'
        remarks = request.data.get('remarks', default_remarks)
        
        # Send notifications to the assigned user
        try:
            import logging
            logger = logging.getLogger(__name__)
            
            # Send email notification
            send_inspection_forward_notification(
                user=next_assignee,
                inspection=inspection,
                forwarded_by=user,
                remarks=remarks
            )
            
            # Create in-app notification
            create_forward_notification(
                recipient=next_assignee,
                inspection=inspection,
                forwarded_by=user,
                remarks=remarks
            )
            
            logger.info(f"Forward notifications sent to {next_assignee.email} for inspection {inspection.code}")
        except Exception as e:
            # Log the error but don't fail the forward operation
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send forward notifications for inspection {inspection.code}: {str(e)}")
        
        # Log history
        
        # Ensure remarks contains "Forwarded" for proper tab filtering
        if 'Forwarded' not in remarks:
            remarks = f'Forwarded: {remarks}'
        
        InspectionHistory.objects.create(
            inspection=inspection,
            previous_status=prev_status,
            new_status=next_status,
            changed_by=user,
            assigned_to=inspection.assigned_to,
            law=inspection.law,
            section=user.section,
            remarks=remarks
        )
        
        # Audit trail for forward action
        audit_inspection_event(
            user,
            inspection,
            AUDIT_ACTIONS["ASSIGN"],
            f"{user.email} forwarded inspection {inspection.code} from {prev_status} to {next_status}",
            request,
            metadata={
                "action": "forward",
                "previous_status": prev_status,
                "new_status": next_status,
                "assigned_to": getattr(next_assignee, "email", None) if next_assignee else None,
                "assigned_userlevel": next_assignee.userlevel if next_assignee else None,
                "remarks": remarks,
            },
        )
        
        serializer = self.get_serializer(inspection)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def review(self, request, pk=None):
        """Review inspection - grants access to view form without changing status"""
        inspection = self.get_object()
        user = request.user
        
        # Check if user can review this inspection
        user_can_review = False
        
        if inspection.assigned_to == user:
            # User is assigned - can always review
            user_can_review = True
        else:
            # User is not assigned - check special cases
            if user.userlevel == 'Unit Head' and inspection.current_status in [
                'UNIT_REVIEWED',
                'MONITORING_IN_PROGRESS',
                'MONITORING_COMPLETED_COMPLIANT',
                'MONITORING_COMPLETED_NON_COMPLIANT',
            ]:
                # Unit Head can review monitoring-stage work even if reassigned
                user_can_review = True
            elif user.userlevel == 'Section Chief' and inspection.current_status in [
                'SECTION_REVIEWED',
                'UNIT_IN_PROGRESS',
                'UNIT_COMPLETED_COMPLIANT',
                'UNIT_COMPLETED_NON_COMPLIANT',
                'UNIT_REVIEWED',
            ]:
                # Section Chief can review unit-stage work even if reassigned
                user_can_review = True
            elif user.userlevel == 'Division Chief' and inspection.current_status in [
                'DIVISION_REVIEWED',
                'SECTION_REVIEWED',
                'SECTION_COMPLETED_COMPLIANT',
                'SECTION_COMPLETED_NON_COMPLIANT',
            ]:
                # Division Chief can review section-level work even if reassigned
                user_can_review = True
            elif user.userlevel == 'Legal Unit' and inspection.current_status == 'LEGAL_REVIEW':
                # Legal Unit can review inspections in LEGAL_REVIEW status even if not assigned
                user_can_review = True
            else:
                user_can_review = False
        
        if not user_can_review:
            return Response(
                {'error': 'You are not authorized to review this inspection'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Review action only grants access - no status change
        return Response({
            'message': 'Review access granted - no status change',
            'status': inspection.current_status,
            'id': inspection.id
        })
    
    @action(detail=True, methods=['post'])
    def review_and_forward_unit(self, request, pk=None):
        """Unit Head reviews and forwards to Section Chief"""
        inspection = self.get_object()
        user = request.user
        
        # Check if user is Unit Head
        if user.userlevel != 'Unit Head':
            return Response(
                {'error': 'Only Unit Heads can perform this action'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check valid statuses
        if inspection.current_status not in ['MONITORING_COMPLETED_COMPLIANT', 'MONITORING_COMPLETED_NON_COMPLIANT']:
            return Response(
                {'error': f'Cannot review from status {inspection.current_status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Handle form data if provided
        form_data = request.data.get('form_data', {})
        if form_data:
            form, created = InspectionForm.objects.get_or_create(inspection=inspection)
            
            # Store all form data in the checklist JSON field
            form.checklist = {
                'general': form_data.get('general', {}),
                'purpose': form_data.get('purpose', {}),
                'permits': form_data.get('permits', []),
                'complianceItems': form_data.get('complianceItems', []),
                'systems': form_data.get('systems', []),
                'recommendationState': form_data.get('recommendationState', {}),
                'lawFilter': form_data.get('lawFilter', []),
                'findingImages': form_data.get('findingImages', {}),
                'generalFindings': form_data.get('generalFindings', []),
                'is_draft': False,
                'completed_at': timezone.now().isoformat(),
                'completed_by': user.id
            }
            
            # Update direct fields from general data
            general_data = form_data.get('general', {})
            if general_data.get('findings_summary'):
                form.findings_summary = general_data['findings_summary']
            if general_data.get('violations_found'):
                form.violations_found = general_data['violations_found']
            if general_data.get('compliance_observations'):
                form.compliance_decision = general_data['compliance_observations']
            if general_data.get('recommendations'):
                form.compliance_plan = general_data['recommendations']
            
            # Update scheduled_at if provided
            if 'general' in form_data and form_data['general'].get('inspection_date_time'):
                try:
                    from datetime import datetime
                    form.scheduled_at = datetime.fromisoformat(form_data['general']['inspection_date_time'].replace('Z', '+00:00'))
                except:
                    pass
            
            # Capture inspector information if this is the first time
            is_first_fill = capture_inspector_info(form, user)
            
            form.save()
        
        # Get Section Chief assignee
        next_assignee = inspection.get_next_assignee('SECTION_REVIEWED')
        if not next_assignee:
            return Response(
                {'error': 'No Section Chief found for assignment'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Transition to UNIT_REVIEWED
        prev_status = inspection.current_status
        inspection.current_status = 'UNIT_REVIEWED'
        inspection.assigned_to = next_assignee
        inspection.save()
        
        # Log history
        remarks = request.data.get('remarks', 'Unit Head reviewed and forwarded to Section Chief')
        InspectionHistory.objects.create(
            inspection=inspection,
            previous_status=prev_status,
            new_status='UNIT_REVIEWED',
            changed_by=user,
            remarks=remarks
        )
        
        # Audit trail for review and forward unit
        audit_inspection_event(
            user,
            inspection,
            AUDIT_ACTIONS["APPROVE"],
            f"{user.email} reviewed and forwarded inspection {inspection.code} to Section Chief",
            request,
            metadata={
                "action": "review_and_forward_unit",
                "previous_status": prev_status,
                "new_status": "UNIT_REVIEWED",
                "assigned_to": getattr(next_assignee, "email", None) if next_assignee else None,
                "remarks": remarks,
            },
        )
        
        # Send notifications to Section Chief
        try:
            # Check if inspection is on non-compliant path
            is_non_compliant = 'NON_COMPLIANT' in prev_status
            
            # For non-compliant: send email + system notification
            if is_non_compliant:
                from .utils import send_inspection_review_notification
                send_inspection_review_notification(inspection, user, next_assignee, 'UNIT_REVIEWED', False)
            
            # For all: create system notification
            from .utils import create_review_notification
            create_review_notification(next_assignee, inspection, user, 'UNIT_REVIEWED', 
                                     request.data.get('remarks', 'Unit Head reviewed'))
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send review notifications for {inspection.code}: {str(e)}")
            # Don't fail the review if notifications fail
        
        serializer = self.get_serializer(inspection)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def review_and_forward_section(self, request, pk=None):
        """Section Chief reviews and forwards to Division Chief"""
        inspection = self.get_object()
        user = request.user
        
        # Check if user is Section Chief
        if user.userlevel != 'Section Chief':
            return Response(
                {'error': 'Only Section Chiefs can perform this action'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check valid statuses based on section type
        valid_statuses = ['UNIT_COMPLETED_COMPLIANT', 'UNIT_COMPLETED_NON_COMPLIANT', 'UNIT_REVIEWED']
        
        # For individual sections (non-combined), also accept MONITORING_COMPLETED
        if user.section != 'PD-1586,RA-8749,RA-9275':
            valid_statuses.extend(['MONITORING_COMPLETED_COMPLIANT', 'MONITORING_COMPLETED_NON_COMPLIANT'])
        
        if inspection.current_status not in valid_statuses:
            return Response(
                {'error': f'Cannot review from status {inspection.current_status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Handle form data if provided
        form_data = request.data.get('form_data', {})
        if form_data:
            form, created = InspectionForm.objects.get_or_create(inspection=inspection)
            
            # Store all form data in the checklist JSON field
            form.checklist = {
                'general': form_data.get('general', {}),
                'purpose': form_data.get('purpose', {}),
                'permits': form_data.get('permits', []),
                'complianceItems': form_data.get('complianceItems', []),
                'systems': form_data.get('systems', []),
                'recommendationState': form_data.get('recommendationState', {}),
                'lawFilter': form_data.get('lawFilter', []),
                'findingImages': form_data.get('findingImages', {}),
                'generalFindings': form_data.get('generalFindings', []),
                'is_draft': False,
                'completed_at': timezone.now().isoformat(),
                'completed_by': user.id
            }
            
            # Update direct fields from general data
            general_data = form_data.get('general', {})
            if general_data.get('findings_summary'):
                form.findings_summary = general_data['findings_summary']
            if general_data.get('violations_found'):
                form.violations_found = general_data['violations_found']
            if general_data.get('compliance_observations'):
                form.compliance_decision = general_data['compliance_observations']
            if general_data.get('recommendations'):
                form.compliance_plan = general_data['recommendations']
            
            # Update scheduled_at if provided
            if 'general' in form_data and form_data['general'].get('inspection_date_time'):
                try:
                    from datetime import datetime
                    form.scheduled_at = datetime.fromisoformat(form_data['general']['inspection_date_time'].replace('Z', '+00:00'))
                except:
                    pass
            
            # Capture inspector information if this is the first time
            is_first_fill = capture_inspector_info(form, user)
            
            form.save()
        
        # Get Division Chief assignee
        next_assignee = inspection.get_next_assignee('DIVISION_REVIEWED')
        if not next_assignee:
            return Response(
                {'error': 'No Division Chief found for assignment'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Transition to SECTION_REVIEWED
        prev_status = inspection.current_status
        inspection.current_status = 'SECTION_REVIEWED'
        inspection.assigned_to = next_assignee
        inspection.save()
        
        # Log history
        remarks = request.data.get('remarks', 'Section Chief reviewed and forwarded to Division Chief')
        InspectionHistory.objects.create(
            inspection=inspection,
            previous_status=prev_status,
            new_status='SECTION_REVIEWED',
            changed_by=user,
            remarks=remarks
        )
        
        # Audit trail for review and forward section
        audit_inspection_event(
            user,
            inspection,
            AUDIT_ACTIONS["APPROVE"],
            f"{user.email} reviewed and forwarded inspection {inspection.code} to Division Chief",
            request,
            metadata={
                "action": "review_and_forward_section",
                "previous_status": prev_status,
                "new_status": "SECTION_REVIEWED",
                "assigned_to": getattr(next_assignee, "email", None) if next_assignee else None,
                "remarks": remarks,
            },
        )
        
        # Send notifications to Division Chief
        try:
            # Check if inspection is on non-compliant path
            is_non_compliant = 'NON_COMPLIANT' in prev_status
            
            # For non-compliant: send email + system notification
            if is_non_compliant:
                from .utils import send_inspection_review_notification
                send_inspection_review_notification(inspection, user, next_assignee, 'SECTION_REVIEWED', False)
            
            # For all: create system notification
            from .utils import create_review_notification
            create_review_notification(next_assignee, inspection, user, 'SECTION_REVIEWED', 
                                     request.data.get('remarks', 'Section Chief reviewed'))
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send review notifications for {inspection.code}: {str(e)}")
            # Don't fail the review if notifications fail
        
        serializer = self.get_serializer(inspection)
        return Response(serializer.data)
        
    
    @action(detail=True, methods=['post'])
    def review_division(self, request, pk=None):
        """Division Chief reviews and marks as DIVISION_REVIEWED"""
        inspection = self.get_object()
        user = request.user
        
        # Check if user is Division Chief
        if user.userlevel != 'Division Chief':
            return Response(
                {'error': 'Only Division Chiefs can perform this action'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check valid status - allow SECTION_REVIEWED and SECTION_COMPLETED_* statuses
        valid_statuses = ['SECTION_REVIEWED', 'SECTION_COMPLETED_COMPLIANT', 'SECTION_COMPLETED_NON_COMPLIANT']
        if inspection.current_status not in valid_statuses:
            return Response(
                {'error': f'Cannot review from status {inspection.current_status}. Expected one of: {", ".join(valid_statuses)}.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate other data using serializer
        serializer = InspectionActionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        # Transition to DIVISION_REVIEWED
        prev_status = inspection.current_status
        inspection.current_status = 'DIVISION_REVIEWED'
        inspection.save()
        
        # Log history
        remarks = data.get('remarks', 'Division Chief reviewed and marked as DIVISION_REVIEWED')
        InspectionHistory.objects.create(
            inspection=inspection,
            previous_status=prev_status,
            new_status='DIVISION_REVIEWED',
            changed_by=user,
            remarks=remarks
        )
        
        # Audit trail for review division
        audit_inspection_event(
            user,
            inspection,
            AUDIT_ACTIONS["APPROVE"],
            f"{user.email} reviewed inspection {inspection.code} and marked as DIVISION_REVIEWED",
            request,
            metadata={
                "action": "review_division",
                "previous_status": prev_status,
                "new_status": "DIVISION_REVIEWED",
                "remarks": remarks,
            },
        )
        
        # Return updated inspection
        response_serializer = InspectionSerializer(inspection, context={'request': request})
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def forward_to_legal(self, request, pk=None):
        """Forward case to Legal Unit (Division Chief only)"""
        inspection = self.get_object()
        user = request.user
        
        # Check if Division Chief
        if user.userlevel != 'Division Chief':
            return Response(
                {'error': 'Only Division Chiefs can forward to Legal Unit'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if in correct status
        if inspection.current_status != 'DIVISION_REVIEWED':
            return Response(
                {'error': 'Can only forward to legal from Division Reviewed status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Removed compliance validation - Division Chief can decide to forward any case to Legal Unit
        
        # Find Legal Unit user
        legal_user = User.objects.filter(userlevel='Legal Unit', is_active=True).first()
        if not legal_user:
            return Response(
                {'error': 'No Legal Unit personnel found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Transition
        prev_status = inspection.current_status
        inspection.current_status = 'LEGAL_REVIEW'
        inspection.assigned_to = legal_user
        inspection.save()
        
        # Log history
        remarks = request.data.get('remarks', 'Forwarded case to Legal Unit')
        InspectionHistory.objects.create(
            inspection=inspection,
            previous_status=prev_status,
            new_status='LEGAL_REVIEW',
            changed_by=user,
            remarks=remarks
        )
        
        # Send notifications to Legal Unit
        try:
            # Send email notification
            send_inspection_forward_notification(
                user=legal_user,
                inspection=inspection,
                forwarded_by=user,
                remarks=remarks
            )
            
            # Create in-app notification
            create_forward_notification(
                recipient=legal_user,
                inspection=inspection,
                forwarded_by=user,
                remarks=remarks
            )
            
            logger.info(f"Forward notifications sent to {legal_user.email} for inspection {inspection.code}")
        except Exception as e:
            # Log the error but don't fail the forward operation
            logger.error(f"Failed to send forward notifications for inspection {inspection.code}: {str(e)}")
        
        # Audit trail for forward to legal
        audit_inspection_event(
            user,
            inspection,
            AUDIT_ACTIONS["ASSIGN"],
            f"{user.email} forwarded inspection {inspection.code} to Legal Unit",
            request,
            metadata={
                "action": "forward_to_legal",
                "previous_status": prev_status,
                "new_status": "LEGAL_REVIEW",
                "assigned_to": getattr(legal_user, "email", None) if legal_user else None,
                "remarks": remarks,
            },
        )
        
        serializer = self.get_serializer(inspection)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def send_nov(self, request, pk=None):
        """Send Notice of Violation (Legal Unit only)"""
        inspection = self.get_object()
        user = request.user
        
        # Check if Legal Unit
        if user.userlevel != 'Legal Unit':
            return Response(
                {'error': 'Only Legal Unit can send NOV'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Validate data
        serializer = NOVSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        # Get or create form
        form, created = InspectionForm.objects.get_or_create(inspection=inspection)
        
        # Create or update NOV record
        nov, nov_created = NoticeOfViolation.objects.get_or_create(
            inspection_form=form,
            defaults={
                'sent_date': timezone.now().date(),
                'violations': data['violations'],
                'compliance_instructions': data['compliance_instructions'],
                'compliance_deadline': data['compliance_deadline'],
                'remarks': data.get('remarks', ''),
                'recipient_email': data['recipient_email'],
                'recipient_name': data.get('recipient_name', ''),
                'contact_person': data.get('contact_person', ''),
                'email_subject': data.get('email_subject', ''),
                'email_body': data.get('email_body', ''),
                'sent_by': user
            }
        )
        
        # If NOV already exists, update it
        if not nov_created:
            nov.sent_date = timezone.now().date()
            nov.violations = data['violations']
            nov.compliance_instructions = data['compliance_instructions']
            nov.compliance_deadline = data['compliance_deadline']
            nov.remarks = data.get('remarks', '')
            nov.recipient_email = data['recipient_email']
            nov.recipient_name = data.get('recipient_name', '')
            nov.contact_person = data.get('contact_person', '')
            nov.email_subject = data.get('email_subject', '')
            nov.email_body = data.get('email_body', '')
            nov.sent_by = user
            nov.save()
        
        # Update violations_found for initial inspection tracking
        form.violations_found = data['violations']
        form.save()
        
        # Transition
        prev_status = inspection.current_status
        inspection.current_status = 'NOV_SENT'
        
        # Send email to recipient
        recipient_email = data.get('recipient_email', '').strip()
        if not recipient_email:
            return Response(
                {'error': 'Recipient email is required to send NOV.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            subject = data.get('email_subject') or f"Notice of Violation – {inspection.code}"
            body = data.get('email_body') or data['violations']
            
            # Get establishment information
            establishment = inspection.establishments.first()
            establishment_name = establishment.name if establishment else 'N/A'
            
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
            
            # Prepare template context
            email_context = {
                'inspection_code': inspection.code,
                'inspection_date': inspection_date,
                'establishment_name': establishment_name,
                'recipient_name': data.get('recipient_name', ''),
                'contact_person': data.get('contact_person', ''),
                'violations': data['violations'],
                'compliance_instructions': data['compliance_instructions'],
                'compliance_deadline': data['compliance_deadline'],
                'remarks': data.get('remarks', ''),
            }
            
            logger.info(f"Attempting to send NOV email to {recipient_email} for inspection {inspection.code}")
            send_notice_email(subject, body, recipient_email, notice_type='NOV', context=email_context)
            logger.info(f"Successfully sent NOV email to {recipient_email} for inspection {inspection.code}")
        except Exception as e:
            logger.error(f"Failed to send NOV email for inspection {inspection.code} to {recipient_email}: {str(e)}", exc_info=True)
            inspection.current_status = prev_status
            inspection.save(update_fields=['current_status'])
            return Response(
                {'error': f'NOV saved but failed to send email: {str(e)}. Please check email configuration and recipient address.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        inspection.save(update_fields=['current_status'])
        
        # Log history
        remarks = data.get('remarks', 'Notice of Violation sent')
        InspectionHistory.objects.create(
            inspection=inspection,
            previous_status=prev_status,
            new_status='NOV_SENT',
            changed_by=user,
            remarks=remarks
        )
        
        # Audit trail for send NOV
        audit_inspection_event(
            user,
            inspection,
            AUDIT_ACTIONS["UPDATE"],
            f"{user.email} sent Notice of Violation for inspection {inspection.code}",
            request,
            metadata={
                "action": "send_nov",
                "previous_status": prev_status,
                "new_status": "NOV_SENT",
                "recipient_email": data['recipient_email'],
                "compliance_deadline": str(data['compliance_deadline']) if data.get('compliance_deadline') else None,
                "remarks": remarks,
            },
        )
        
        serializer = self.get_serializer(inspection)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def send_noo(self, request, pk=None):
        """Send Notice of Order (Legal Unit only)"""
        inspection = self.get_object()
        user = request.user
        
        # Check if Legal Unit
        if user.userlevel != 'Legal Unit':
            return Response(
                {'error': 'Only Legal Unit can send NOO'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Validate data
        serializer = NOOSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        # Get or create form
        form, created = InspectionForm.objects.get_or_create(inspection=inspection)
        
        # Create or update NOO record
        noo, noo_created = NoticeOfOrder.objects.get_or_create(
            inspection_form=form,
            defaults={
                'sent_date': timezone.now().date(),
                'violation_breakdown': data['violation_breakdown'],
                'penalty_fees': data['penalty_fees'],
                'payment_deadline': data['payment_deadline'],
                'payment_instructions': data.get('payment_instructions', ''),
                'remarks': data.get('remarks', ''),
                'recipient_email': data['recipient_email'],
                'recipient_name': data.get('recipient_name', ''),
                'contact_person': data.get('contact_person', ''),
                'email_subject': data.get('email_subject', ''),
                'email_body': data.get('email_body', ''),
                'sent_by': user
            }
        )
        
        # If NOO already exists, update it
        if not noo_created:
            noo.sent_date = timezone.now().date()
            noo.violation_breakdown = data['violation_breakdown']
            noo.penalty_fees = data['penalty_fees']
            noo.payment_deadline = data['payment_deadline']
            noo.payment_instructions = data.get('payment_instructions', '')
            noo.remarks = data.get('remarks', '')
            noo.recipient_email = data['recipient_email']
            noo.recipient_name = data.get('recipient_name', '')
            noo.contact_person = data.get('contact_person', '')
            noo.email_subject = data.get('email_subject', '')
            noo.email_body = data.get('email_body', '')
            noo.sent_by = user
            noo.save()
        
        # Transition
        prev_status = inspection.current_status
        
        # Get establishment information
        establishment = inspection.establishments.first()
        if not establishment:
            return Response(
                {'error': 'No establishment associated with this inspection'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate that inspection has a law (required for billing record)
        if not inspection.law:
            logger.error(f"Cannot create billing record for inspection {inspection.code}: inspection.law is None")
            return Response(
                {'error': 'Inspection must have a law associated before sending NOO. Please ensure the inspection has a law assigned.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create billing record first (so billing_code is available for email)
        try:
            # Use get_or_create to handle existing billing records
            # Since BillingRecord has OneToOneField with Inspection, there can only be one per inspection
            billing, created = BillingRecord.objects.get_or_create(
                inspection=inspection,
                defaults={
                    'establishment': establishment,
                    'establishment_name': establishment.name,
                    'contact_person': getattr(establishment, 'contact_person', ''),
                    'related_law': inspection.law,
                    'billing_type': 'PENALTY',
                    'description': data['violation_breakdown'],
                    'amount': data['penalty_fees'],
                    'due_date': data['payment_deadline'],
                    'recommendations': data.get('remarks', ''),
                    'issued_by': user
                }
            )
            
            # If billing record already exists, update it with new data
            if not created:
                billing.establishment = establishment
                billing.establishment_name = establishment.name
                billing.contact_person = getattr(establishment, 'contact_person', '')
                billing.related_law = inspection.law
                billing.billing_type = 'PENALTY'
                billing.description = data['violation_breakdown']
                billing.amount = data['penalty_fees']
                billing.due_date = data['payment_deadline']
                billing.recommendations = data.get('remarks', '')
                billing.issued_by = user
                billing.save()
                logger.info(f"Updated existing billing record for inspection {inspection.code}")
            else:
                logger.info(f"Created new billing record for inspection {inspection.code}")
                
        except Exception as e:
            logger.error(f"Failed to create/update billing record for inspection {inspection.code}: {str(e)}", exc_info=True)
            return Response(
                {'error': f'Failed to create/update billing record: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Update inspection status
        inspection.current_status = 'NOO_SENT'
        
        # Send email to recipient
        recipient_email = data.get('recipient_email', '').strip()
        if not recipient_email:
            inspection.current_status = prev_status
            inspection.save(update_fields=['current_status'])
            return Response(
                {'error': 'Recipient email is required to send NOO.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            subject = data.get('email_subject') or f"Notice of Order – {inspection.code}"
            body = data.get('email_body') or data['violation_breakdown']
            
            establishment_name = establishment.name if establishment else 'N/A'
            
            # Get inspection date from form if available
            inspection_date = 'N/A'
            nov_date = None
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
                    # Try to get NOV sent date
                    if hasattr(inspection.form, 'nov') and inspection.form.nov:
                        if inspection.form.nov.sent_date:
                            nov_date = inspection.form.nov.sent_date.strftime('%B %d, %Y')
                except Exception:
                    pass
            
            # Prepare template context with billing code
            email_context = {
                'inspection_code': inspection.code,
                'inspection_date': inspection_date,
                'nov_date': nov_date,
                'establishment_name': establishment_name,
                'recipient_name': data.get('recipient_name', ''),
                'contact_person': data.get('contact_person', ''),
                'violation_breakdown': data['violation_breakdown'],
                'penalty_fees': data['penalty_fees'],
                'payment_deadline': data['payment_deadline'],
                'payment_instructions': data.get('payment_instructions', ''),
                'remarks': data.get('remarks', ''),
                'billing_code': billing.billing_code if billing else None,
            }
            
            logger.info(f"Attempting to send NOO email to {recipient_email} for inspection {inspection.code}")
            send_notice_email(subject, body, recipient_email, notice_type='NOO', context=email_context)
            logger.info(f"Successfully sent NOO email to {recipient_email} for inspection {inspection.code}")
        except Exception as e:
            logger.error(f"Failed to send NOO email for inspection {inspection.code} to {recipient_email}: {str(e)}", exc_info=True)
            inspection.current_status = prev_status
            inspection.save(update_fields=['current_status'])
            return Response(
                {'error': f'NOO saved but failed to send email: {str(e)}. Please check email configuration and recipient address.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        inspection.save(update_fields=['current_status'])
        
        # Log history
        remarks = f"Notice of Order sent. Penalties: ₱{data['penalty_fees']}"
        InspectionHistory.objects.create(
            inspection=inspection,
            previous_status=prev_status,
            new_status='NOO_SENT',
            changed_by=user,
            remarks=remarks
        )
        
        # Audit trail for send NOO
        audit_inspection_event(
            user,
            inspection,
            AUDIT_ACTIONS["UPDATE"],
            f"{user.email} sent Notice of Order for inspection {inspection.code}",
            request,
            metadata={
                "action": "send_noo",
                "previous_status": prev_status,
                "new_status": "NOO_SENT",
                "recipient_email": data['recipient_email'],
                "payment_deadline": str(data['payment_deadline']) if data.get('payment_deadline') else None,
                "billing_code": billing.billing_code if billing else None,
                "penalty_fees": str(data['penalty_fees']),
                "remarks": remarks,
            },
        )
        
        serializer = self.get_serializer(inspection)
        return Response({
            'inspection': serializer.data,
            'billing': {
                'id': billing.id,
                'billing_code': billing.billing_code,
                'amount': str(billing.amount)
            }
        })
    
    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """Close inspection (Section/Division/Legal)"""
        inspection = self.get_object()
        user = request.user
        
        if user.userlevel == 'Section Chief' and inspection.current_status == 'SECTION_REVIEWED':
            # Section Chief closing - send to Division
            next_assignee = inspection.get_next_assignee('DIVISION_REVIEWED')
            if not next_assignee:
                return Response({'error': 'No Division Chief found'}, status=status.HTTP_404_NOT_FOUND)
            
            prev_status = inspection.current_status
            inspection.current_status = 'DIVISION_REVIEWED'
            inspection.assigned_to = next_assignee
            inspection.save()
            
            remarks = request.data.get('remarks', 'Closed by Section Chief')
            InspectionHistory.objects.create(
                inspection=inspection,
                previous_status=prev_status,
                new_status='DIVISION_REVIEWED',
                changed_by=user,
                remarks=remarks
            )
            
            # Audit trail for close (Section Chief)
            audit_inspection_event(
                user,
                inspection,
                AUDIT_ACTIONS["UPDATE"],
                f"{user.email} closed inspection {inspection.code} and forwarded to Division Chief",
                request,
                metadata={
                    "action": "close_section_chief",
                    "previous_status": prev_status,
                    "new_status": "DIVISION_REVIEWED",
                    "assigned_to": getattr(next_assignee, "email", None) if next_assignee else None,
                    "remarks": remarks,
                },
            )
            
        elif user.userlevel == 'Division Chief' and inspection.current_status in ['DIVISION_REVIEWED', 'SECTION_COMPLETED_COMPLIANT', 'SECTION_COMPLETED_NON_COMPLIANT']:
            # Division Chief finalizing
            final_status = request.data.get('final_status', 'CLOSED')
            
            prev_status = inspection.current_status
            inspection.current_status = final_status
            inspection.assigned_to = None
            inspection.save()
            
            remarks = request.data.get('remarks', 'Closed by Division Chief')
            InspectionHistory.objects.create(
                inspection=inspection,
                previous_status=prev_status,
                new_status=final_status,
                changed_by=user,
                remarks=remarks
            )
            
            # Audit trail for close (Division Chief)
            audit_inspection_event(
                user,
                inspection,
                AUDIT_ACTIONS["UPDATE"],
                f"{user.email} closed inspection {inspection.code} as {final_status}",
                request,
                metadata={
                    "action": "close_division_chief",
                    "previous_status": prev_status,
                    "new_status": final_status,
                    "assigned_to": None,
                    "remarks": remarks,
                },
            )
            
        elif user.userlevel == 'Legal Unit' and inspection.current_status in ['LEGAL_REVIEW', 'NOV_SENT', 'NOO_SENT']:
            # Legal Unit finalizing
            final_status = request.data.get('final_status', 'CLOSED_NON_COMPLIANT')
            
            prev_status = inspection.current_status
            inspection.current_status = final_status
            inspection.assigned_to = None
            inspection.save()
            
            remarks = request.data.get('remarks', 'Legal review completed')
            InspectionHistory.objects.create(
                inspection=inspection,
                previous_status=prev_status,
                new_status=final_status,
                changed_by=user,
                remarks=remarks
            )
            
            # Audit trail for close (Legal Unit)
            audit_inspection_event(
                user,
                inspection,
                AUDIT_ACTIONS["UPDATE"],
                f"{user.email} closed inspection {inspection.code} as {final_status}",
                request,
                metadata={
                    "action": "close_legal_unit",
                    "previous_status": prev_status,
                    "new_status": final_status,
                    "assigned_to": None,
                    "remarks": remarks,
                },
            )
        else:
            return Response(
                {'error': 'Invalid status or user level for close action'},
                status=status.HTTP_400_BAD_REQUEST
        )
        
        serializer = self.get_serializer(inspection)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def return_to_division(self, request, pk=None):
        """Legal Unit returns inspection to Division Chief"""
        inspection = self.get_object()
        user = request.user
        
        # Check if user is Legal Unit
        if user.userlevel != 'Legal Unit':
            return Response(
                {'error': 'Only Legal Unit can perform this action'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check valid status
        if inspection.current_status != 'LEGAL_REVIEW':
            return Response(
                {'error': f'Cannot return from status {inspection.current_status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Find Division Chief assignee
        next_assignee = inspection.get_next_assignee('DIVISION_REVIEWED')
        if not next_assignee:
            return Response(
                {'error': 'No Division Chief found for assignment'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Transition back to DIVISION_REVIEWED
        prev_status = inspection.current_status
        inspection.current_status = 'DIVISION_REVIEWED'
        inspection.assigned_to = next_assignee
        
        # Clear signatures when returning inspection
        self._clear_signatures_on_return(inspection)
        
        inspection.save()
        
        # Log history
        remarks = request.data.get('remarks', 'Returned to Division Chief by Legal Unit')
        InspectionHistory.objects.create(
            inspection=inspection,
            previous_status=prev_status,
            new_status='DIVISION_REVIEWED',
            changed_by=user,
            assigned_to=next_assignee,
            law=inspection.law,
            section=user.section,
            remarks=remarks
        )
        
        # Audit trail for return to division
        audit_inspection_event(
            user,
            inspection,
            AUDIT_ACTIONS["UPDATE"],
            f"{user.email} returned inspection {inspection.code} to Division Chief",
            request,
            metadata={
                "action": "return_to_division",
                "previous_status": prev_status,
                "new_status": "DIVISION_REVIEWED",
                "assigned_to": getattr(next_assignee, "email", None) if next_assignee else None,
                "remarks": remarks,
            },
        )
        
        serializer = self.get_serializer(inspection)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='compliance-expired')
    def check_compliance_expired(self, request):
        """Check for inspections with expired compliance deadlines (Legal Unit only)"""
        user = request.user
        
        # Check if Legal Unit
        if user.userlevel != 'Legal Unit':
            return Response(
                {'error': 'Only Legal Unit can access this endpoint'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        from .models import InspectionForm
        
        # Find inspections with expired NOV compliance deadlines
        expired = []
        now = timezone.now()
        
        # Query inspections in NOV_SENT or NOO_SENT with expired deadlines
        inspections = Inspection.objects.filter(
            current_status__in=['NOV_SENT', 'NOO_SENT']
        ).select_related('form')
        
        for inspection in inspections:
            form = getattr(inspection, 'form', None)
            if form and form.nov_compliance_date:
                if form.nov_compliance_date < now:
                    days_overdue = (now.date() - form.nov_compliance_date.date()).days
                    expired.append({
                        'id': inspection.id,
                        'code': inspection.code,
                        'establishment': inspection.establishments.first().name if inspection.establishments.exists() else 'N/A',
                        'status': inspection.current_status,
                        'compliance_deadline': form.nov_compliance_date,
                        'days_overdue': days_overdue,
                        'violations': form.nov_violations or form.violations_found
                    })
        
        return Response({
            'count': len(expired),
            'expired_inspections': expired
        })
    
    @action(detail=False, methods=['get'])
    def compliance_stats(self, request):
        """
        Get compliance statistics based on InspectionForm.compliance_decision
        """
        from django.db.models import Count, Q
        from .models import InspectionForm
        
        # Get compliance statistics
        stats = InspectionForm.objects.aggregate(
            pending=Count('inspection_id', filter=Q(compliance_decision='PENDING')),
            compliant=Count('inspection_id', filter=Q(compliance_decision='COMPLIANT')),
            non_compliant=Count('inspection_id', filter=Q(compliance_decision__in=['NON_COMPLIANT', 'PARTIALLY_COMPLIANT']))
        )
        
        # Calculate total completed
        stats['total_completed'] = stats['compliant'] + stats['non_compliant']
        
        return Response(stats)
    
    @action(detail=False, methods=['get'])
    def quarterly_comparison(self, request):
        """
        Get comparison data for finished inspections with optional law filtering.
        Supports monthly, quarterly, and yearly period types.
        """
        from django.db.models import Count, Q
        from .models import InspectionForm
        from datetime import datetime, timedelta
        from django.utils import timezone as tz
        from calendar import month_name
        
        # Get period type (monthly, quarterly, yearly) - default to quarterly for backward compatibility
        period_type = request.query_params.get('period_type', 'quarterly')
        if period_type not in ['monthly', 'quarterly', 'yearly']:
            period_type = 'quarterly'
        
        # Get year parameter (default to current year)
        year = int(request.query_params.get('year', datetime.now().year))
        
        # Get law parameter for filtering
        law_filter = request.query_params.get('law', 'all')
        
        # Define law choices
        law_choices = [
            ("PD-1586", "PD-1586 (EIA)"),
            ("RA-6969", "RA-6969 (TOX)"),
            ("RA-8749", "RA-8749 (CAA)"),
            ("RA-9275", "RA-9275 (CWA)"),
            ("RA-9003", "RA-9003 (SWM)")
        ]
        
        # Helper functions for date ranges
        def get_quarter_range(year, quarter):
            """Get start and end dates for a quarter"""
            if quarter == 1:
                return tz.datetime(year, 1, 1, 0, 0, 0), tz.datetime(year, 3, 31, 23, 59, 59)
            elif quarter == 2:
                return tz.datetime(year, 4, 1, 0, 0, 0), tz.datetime(year, 6, 30, 23, 59, 59)
            elif quarter == 3:
                return tz.datetime(year, 7, 1, 0, 0, 0), tz.datetime(year, 9, 30, 23, 59, 59)
            else:  # quarter == 4
                return tz.datetime(year, 10, 1, 0, 0, 0), tz.datetime(year, 12, 31, 23, 59, 59)
        
        def get_month_range(year, month):
            """Get start and end dates for a month"""
            if month == 12:
                end_date = tz.datetime(year + 1, 1, 1, 0, 0, 0) - timedelta(seconds=1)
            else:
                end_date = tz.datetime(year, month + 1, 1, 0, 0, 0) - timedelta(seconds=1)
            return tz.datetime(year, month, 1, 0, 0, 0), end_date
        
        def get_year_range(year):
            """Get start and end dates for a year"""
            return tz.datetime(year, 1, 1, 0, 0, 0), tz.datetime(year, 12, 31, 23, 59, 59)
        
        # Get current date info
        now = datetime.now()
        current_year = now.year
        current_month = now.month
        current_quarter = ((current_month - 1) // 3) + 1
        
        # Calculate date ranges based on period type
        if period_type == 'monthly':
            # Current month vs previous month
            current_start, current_end = get_month_range(current_year, current_month)
            
            # Calculate previous month
            if current_month == 1:
                last_month = 12
                last_year = current_year - 1
            else:
                last_month = current_month - 1
                last_year = current_year
            
            last_start, last_end = get_month_range(last_year, last_month)
            
            # Format labels
            def get_period_label(year, month):
                month_abbr = month_name[month][:3] if month_name[month] else f"Month {month}"
                return f"{month_abbr} {year}"
            
            current_period_label = get_period_label(current_year, current_month)
            last_period_label = get_period_label(last_year, last_month)
            
        elif period_type == 'yearly':
            # Current year vs previous year
            current_start, current_end = get_year_range(current_year)
            last_year = current_year - 1
            last_start, last_end = get_year_range(last_year)
            
            # Format labels
            current_period_label = str(current_year)
            last_period_label = str(last_year)
            
        else:  # quarterly (default)
            # Current quarter vs previous quarter
            if current_quarter == 1:
                last_quarter = 4
                last_year = current_year - 1
            else:
                last_quarter = current_quarter - 1
                last_year = current_year
            
            current_start, current_end = get_quarter_range(current_year, current_quarter)
            last_start, last_end = get_quarter_range(last_year, last_quarter)
            
            # Format labels
            def get_quarter_name(quarter_num, year):
                quarter_names = {
                    1: 'Jan-Mar',
                    2: 'Apr-Jun', 
                    3: 'Jul-Sep',
                    4: 'Oct-Dec'
                }
                return f"{quarter_names[quarter_num]} {year}"
            
            current_period_label = get_quarter_name(current_quarter, current_year)
            last_period_label = get_quarter_name(last_quarter, last_year)
        
        # Build base query filters
        base_filters = {
            'compliance_decision__in': ['COMPLIANT', 'NON_COMPLIANT', 'PARTIALLY_COMPLIANT']
        }
        
        # Add law filter if specified
        if law_filter != 'all' and law_filter in [choice[0] for choice in law_choices]:
            base_filters['inspection__law'] = law_filter
        
        # Get current period stats (only finished inspections - not PENDING)
        current_filters = {
            'created_at__range': [current_start, current_end],
            **base_filters
        }
        current_stats = InspectionForm.objects.filter(**current_filters).aggregate(
            compliant=Count('inspection_id', filter=Q(compliance_decision='COMPLIANT')),
            non_compliant=Count('inspection_id', filter=Q(compliance_decision__in=['NON_COMPLIANT', 'PARTIALLY_COMPLIANT']))
        )
        
        # Get last period stats (only finished inspections - not PENDING)
        last_filters = {
            'created_at__range': [last_start, last_end],
            **base_filters
        }
        last_stats = InspectionForm.objects.filter(**last_filters).aggregate(
            compliant=Count('inspection_id', filter=Q(compliance_decision='COMPLIANT')),
            non_compliant=Count('inspection_id', filter=Q(compliance_decision__in=['NON_COMPLIANT', 'PARTIALLY_COMPLIANT']))
        )
        
        # Calculate totals
        current_total = current_stats['compliant'] + current_stats['non_compliant']
        last_total = last_stats['compliant'] + last_stats['non_compliant']
        
        # Calculate percentage change
        if last_total > 0:
            change_percentage = ((current_total - last_total) / last_total) * 100
        else:
            change_percentage = 100.0 if current_total > 0 else 0.0
        
        # Determine trend
        if change_percentage > 5:
            trend = 'up'
        elif change_percentage < -5:
            trend = 'down'
        else:
            trend = 'stable'
        
        # Get law name for display
        law_name = None
        if law_filter != 'all':
            for choice in law_choices:
                if choice[0] == law_filter:
                    law_name = choice[1]
                    break
        
        # Build response with period-agnostic structure
        response_data = {
            'current_period': {
                'period': current_period_label,
                'year': current_year if period_type != 'yearly' else current_year,
                'compliant': current_stats['compliant'],
                'non_compliant': current_stats['non_compliant'],
                'total_finished': current_total
            },
            'last_period': {
                'period': last_period_label,
                'year': last_year if period_type != 'yearly' else last_year,
                'compliant': last_stats['compliant'],
                'non_compliant': last_stats['non_compliant'],
                'total_finished': last_total
            },
            'change_percentage': round(change_percentage, 1),
            'trend': trend,
            'period_type': period_type,
            'filter': {
                'law': law_filter,
                'law_name': law_name,
                'is_filtered': law_filter != 'all'
            }
        }
        
        # For backward compatibility, also include old structure
        response_data['current_quarter'] = response_data['current_period']
        response_data['last_quarter'] = response_data['last_period']
        
        return Response(response_data)
    
    @action(detail=False, methods=['get'])
    def compliance_by_law(self, request):
        """
        Get compliance statistics grouped by law with role-based filtering.
        Supports monthly, quarterly, and yearly period filtering (defaults to quarterly).
        """
        from django.db.models import Count, Q
        from .models import InspectionForm, Inspection
        from datetime import datetime, timedelta
        from django.utils import timezone as tz
        from calendar import month_name
        
        # Get period type (monthly, quarterly, yearly) - default to 'quarterly'
        period_type = request.query_params.get('period_type', 'quarterly')
        if period_type not in ['monthly', 'quarterly', 'yearly']:
            period_type = 'quarterly'
        
        user = request.user
        law_choices = [
            ("PD-1586", "PD-1586 (EIA)"),
            ("RA-6969", "RA-6969 (TOX)"),
            ("RA-8749", "RA-8749 (AIR)"),
            ("RA-9275", "RA-9275 (WATER)"),
            ("RA-9003", "RA-9003 (WASTE)")
        ]
        
        # Helper functions for date ranges (same as quarterly_comparison)
        def get_quarter_range(year, quarter):
            """Get start and end dates for a quarter"""
            if quarter == 1:
                return tz.datetime(year, 1, 1, 0, 0, 0), tz.datetime(year, 3, 31, 23, 59, 59)
            elif quarter == 2:
                return tz.datetime(year, 4, 1, 0, 0, 0), tz.datetime(year, 6, 30, 23, 59, 59)
            elif quarter == 3:
                return tz.datetime(year, 7, 1, 0, 0, 0), tz.datetime(year, 9, 30, 23, 59, 59)
            else:  # quarter == 4
                return tz.datetime(year, 10, 1, 0, 0, 0), tz.datetime(year, 12, 31, 23, 59, 59)
        
        def get_month_range(year, month):
            """Get start and end dates for a month"""
            if month == 12:
                end_date = tz.datetime(year + 1, 1, 1, 0, 0, 0) - timedelta(seconds=1)
            else:
                end_date = tz.datetime(year, month + 1, 1, 0, 0, 0) - timedelta(seconds=1)
            return tz.datetime(year, month, 1, 0, 0, 0), end_date
        
        def get_year_range(year):
            """Get start and end dates for a year"""
            return tz.datetime(year, 1, 1, 0, 0, 0), tz.datetime(year, 12, 31, 23, 59, 59)
        
        # Calculate date range based on period type
        now = datetime.now()
        current_year = now.year
        current_month = now.month
        current_quarter = ((current_month - 1) // 3) + 1
        
        if period_type == 'monthly':
            current_start, current_end = get_month_range(current_year, current_month)
        elif period_type == 'quarterly':
            current_start, current_end = get_quarter_range(current_year, current_quarter)
        else:  # yearly
            current_start, current_end = get_year_range(current_year)
        
        date_filter = Q(created_at__range=[current_start, current_end])
        
        # Get selected laws from query parameter
        selected_laws = request.query_params.getlist('laws')
        if selected_laws:
            law_choices = [(code, name) for code, name in law_choices if code in selected_laws]
        
        # Section-based filtering for Section Chief and Unit Head
        if user.userlevel in ['Section Chief', 'Unit Head']:
            if user.section == 'PD-1586,RA-8749,RA-9275':
                # Combined EIA section - show PD-1586, RA-8749, RA-9275
                allowed_laws = ['PD-1586', 'RA-8749', 'RA-9275']
            else:
                # Single section - show only that law
                allowed_laws = [user.section]
            
            # Filter law_choices to only include allowed laws
            law_choices = [(code, name) for code, name in law_choices if code in allowed_laws]
        
        stats_by_law = []
        
        for law_code, law_name in law_choices:
            # Get base inspection queryset for this law
            base_inspections = Inspection.objects.filter(law=law_code)
            
            # Apply role-based filtering (similar to get_queryset logic)
            if user.userlevel == 'Admin':
                # Admin sees all inspections
                filtered_inspections = base_inspections
            elif user.userlevel == 'Division Chief':
                # Division Chief sees inspections they created or are assigned for review
                filtered_inspections = base_inspections.filter(
                    Q(created_by=user) | Q(current_status='DIVISION_REVIEWED')
                )
            elif user.userlevel == 'Section Chief':
                # Section Chief sees inspections related to their section
                if user.section == 'PD-1586,RA-8749,RA-9275':
                    # Special case for combined EIA section
                    filtered_inspections = base_inspections.filter(
                        Q(assigned_to=user) | 
                        Q(law__in=['PD-1586', 'RA-8749', 'RA-9275'])
                    )
                else:
                    filtered_inspections = base_inspections.filter(
                        Q(assigned_to=user) | Q(law=user.section)
                    )
            elif user.userlevel == 'Unit Head':
                # Unit Head sees inspections related to their section
                if user.section == 'PD-1586,RA-8749,RA-9275':
                    # Special case for combined EIA section
                    filtered_inspections = base_inspections.filter(
                        Q(assigned_to=user) | 
                        Q(law__in=['PD-1586', 'RA-8749', 'RA-9275'])
                    )
                else:
                    filtered_inspections = base_inspections.filter(
                        Q(assigned_to=user) | Q(law=user.section)
                    )
            elif user.userlevel == 'Monitoring Personnel':
                # Monitoring Personnel sees inspections assigned to them
                filtered_inspections = base_inspections.filter(assigned_to=user)
            elif user.userlevel == 'Legal Unit':
                # Legal Unit sees inspections in legal review status
                filtered_inspections = base_inspections.filter(
                    current_status__in=['LEGAL_REVIEW', 'NOV_SENT', 'NOO_SENT']
                )
            else:
                # Default: only see inspections assigned to user
                filtered_inspections = base_inspections.filter(assigned_to=user)
            
            # Get inspection IDs for compliance stats
            inspection_ids = filtered_inspections.values_list('id', flat=True)
            
            # Build compliance stats query with optional date filter
            compliance_query = Q(inspection_id__in=inspection_ids)
            if date_filter:
                compliance_query &= date_filter
            
            # Get compliance stats for these inspections
            law_stats = InspectionForm.objects.filter(compliance_query).aggregate(
                pending=Count('inspection_id', filter=Q(compliance_decision='PENDING')),
                compliant=Count('inspection_id', filter=Q(compliance_decision='COMPLIANT')),
                non_compliant=Count('inspection_id', filter=Q(compliance_decision__in=['NON_COMPLIANT', 'PARTIALLY_COMPLIANT']))
            )
            
            total = law_stats['pending'] + law_stats['compliant'] + law_stats['non_compliant']
            
            stats_by_law.append({
                'law': law_code,
                'law_name': law_name,
                'pending': law_stats['pending'],
                'compliant': law_stats['compliant'],
                'non_compliant': law_stats['non_compliant'],
                'total': total
            })
        
        # Return data with period_type for frontend reference
        return Response({
            'data': stats_by_law,
            'period_type': period_type
        })
    
    @action(detail=False, methods=['get'])
    def tab_counts(self, request):
        """Get tab counts for role-based dashboard"""
        from django.http import QueryDict
        
        user = request.user
        
        # Define tab mappings (simplified - use existing get_queryset logic)
        tab_list = {
            'Admin': ['all_inspections', 'compliant', 'non_compliant'],
            'Division Chief': ['all_inspections', 'review', 'reviewed', 'compliant', 'non_compliant'],
            'Section Chief': ['section_assigned', 'section_in_progress', 'forwarded', 'inspection_complete', 'review', 'under_review', 'compliant', 'non_compliant'],
            'Unit Head': ['unit_assigned', 'unit_in_progress', 'forwarded', 'inspection_complete', 'review', 'under_review', 'compliant', 'non_compliant'],
            'Monitoring Personnel': ['assigned', 'in_progress', 'inspection_complete', 'under_review', 'compliant', 'non_compliant'],
            'Legal Unit': ['legal_review', 'nov_sent', 'noo_sent', 'compliant', 'non_compliant']
        }
        
        user_level = user.userlevel
        tabs = tab_list.get(user_level, [])
        counts = {}
        
        # Save original query params
        original_params = self.request.query_params
        
        for tab_name in tabs:
            # Create a mutable copy of query params and set tab
            query_params = QueryDict('', mutable=True)
            query_params.update(original_params)
            query_params['tab'] = tab_name
            
            # Temporarily replace query_params
            self.request._request.GET = query_params
            
            # Get queryset with tab filtering applied
            queryset = self.get_queryset()
            counts[tab_name] = queryset.count()
        
        # Restore original query params
        self.request._request.GET = original_params
        
        return Response(counts)

    @action(detail=False, methods=['get'])
    def get_quotas(self, request):
        """Get quotas with support for monthly, quarterly, and yearly views"""
        from datetime import datetime
        from .models import ComplianceQuota
        
        user = request.user
        year = int(request.query_params.get('year', datetime.now().year))
        # Accept both snake_case and camelCase for view_mode
        view_mode = request.query_params.get('view_mode') or request.query_params.get('viewMode', 'monthly')
        
        # Support both month and quarter parameters (month takes precedence)
        month = request.query_params.get('month')
        quarter = request.query_params.get('quarter')
        
        # Base queryset - filter by month or quarter
        if view_mode == 'yearly':
            # For yearly view, get all monthly quotas for the year
            quotas = ComplianceQuota.objects.filter(year=year)
        elif view_mode == 'monthly' and month:
            # For monthly view, filter by specific month
            month = int(month)
            quotas = ComplianceQuota.objects.filter(year=year, month=month)
        elif view_mode == 'quarterly' and quarter:
            # For quarterly view, get all months in the quarter
            quarter = int(quarter)
            quarter_months = ComplianceQuota.get_months_in_quarter(quarter)
            quotas = ComplianceQuota.objects.filter(year=year, month__in=quarter_months)
        else:
            # Default to current quarter
            quarter = ((datetime.now().month - 1) // 3) + 1
            quarter_months = ComplianceQuota.get_months_in_quarter(quarter)
            quotas = ComplianceQuota.objects.filter(year=year, month__in=quarter_months)
        
        # Apply role-based filtering
        if user.userlevel == 'Section Chief':
            if hasattr(user, 'section') and user.section:
                if user.section == 'PD-1586,RA-8749,RA-9275':
                    # Combined section: show 3 laws
                    quotas = quotas.filter(law__in=['PD-1586', 'RA-8749', 'RA-9275'])
                else:
                    # Individual section: show only their law
                    quotas = quotas.filter(law=user.section)
        elif user.userlevel == 'Unit Head':
            if hasattr(user, 'section') and user.section:
                # Unit Heads always see only their specific law
                quotas = quotas.filter(law=user.section)
        # Admin and Division Chief see all quotas (no filter)
        
        quota_data = []
        
        # For quarterly and yearly views, aggregate monthly quotas by law
        if view_mode == 'quarterly' or view_mode == 'yearly':
            # Group quotas by law and aggregate
            from collections import defaultdict
            aggregated_quotas = defaultdict(lambda: {
                'target': 0,
                'accomplished': 0,
                'months': [],
                'quota_obj': None,
                'auto_adjusted': False
            })
            
            for quota in quotas:
                law_key = quota.law
                aggregated_quotas[law_key]['target'] += quota.target
                aggregated_quotas[law_key]['accomplished'] += quota.accomplished
                aggregated_quotas[law_key]['months'].append(quota.month)
                # Keep the first quota object for metadata (id, year, etc.)
                if aggregated_quotas[law_key]['quota_obj'] is None:
                    aggregated_quotas[law_key]['quota_obj'] = quota
                # If any quota is auto-adjusted, mark as auto-adjusted
                if quota.auto_adjusted:
                    aggregated_quotas[law_key]['auto_adjusted'] = True
            
            # Convert aggregated data to response format
            for law, data in aggregated_quotas.items():
                quota = data['quota_obj']
                total_target = data['target']
                total_accomplished = data['accomplished']
                
                percentage = round((total_accomplished / total_target * 100), 1) if total_target > 0 else 0
                exceeded = total_accomplished > total_target
                
                quota_data.append({
                    'id': quota.id,  # Use first quota's ID
                    'law': law,
                    'year': quota.year,
                    'quarter': quota.quarter if view_mode == 'quarterly' else None,  # Only set quarter for quarterly view
                    'month': None,  # No specific month for aggregated views
                    'target': total_target,
                    'accomplished': total_accomplished,
                    'auto_adjusted': data['auto_adjusted'],
                    'percentage': percentage,
                    'exceeded': exceeded,
                    'created_at': quota.created_at,
                    'updated_at': quota.updated_at
                })
        else:
            # For monthly view only, return individual records
            for quota in quotas:
                # Use actual month from quota
                month_value = quota.month
                
                # For monthly view, use month-specific accomplished
                accomplished = quota.accomplished  # Already uses month dates
                
                # Calculate percentage and exceeded status
                percentage = round((accomplished / quota.target * 100), 1) if quota.target > 0 else 0
                exceeded = accomplished > quota.target
                
                quota_data.append({
                    'id': quota.id,
                    'law': quota.law,
                    'year': quota.year,
                    'quarter': quota.quarter,
                    'month': quota.month,  # Return actual month
                    'target': quota.target,  # Monthly target
                    'accomplished': accomplished,  # Month-specific accomplished
                    'auto_adjusted': quota.auto_adjusted,
                    'percentage': percentage,
                    'exceeded': exceeded,
                    'created_at': quota.created_at,
                    'updated_at': quota.updated_at
                })
        
        return Response(quota_data)

    @action(detail=False, methods=['post'])
    def set_quota(self, request):
        """Set or update quota(s) - supports single or bulk creation"""
        from datetime import datetime
        from .models import ComplianceQuota
        
        # Check if it's a list (bulk) or single quota
        data = request.data
        if isinstance(data, list):
            # Bulk create/update
            results = []
            errors = []
            for quota_data in data:
                try:
                    result = self._create_single_quota(quota_data, request.user)
                    results.append(result)
                except Exception as e:
                    errors.append({
                        'law': quota_data.get('law'),
                        'month': quota_data.get('month'),
                        'error': str(e)
                    })
            
            if errors:
                return Response(
                    {
                        'results': results,
                        'errors': errors,
                        'message': f'Created {len(results)} quotas, {len(errors)} failed'
                    },
                    status=status.HTTP_207_MULTI_STATUS
                )
            return Response({
                'results': results,
                'message': f'Successfully created {len(results)} quotas'
            })
        else:
            # Single quota
            try:
                result = self._create_single_quota(data, request.user)
                return Response(result)
            except Exception as e:
                return Response(
                    {'error': str(e)}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
    
    def _create_single_quota(self, quota_data, user):
        """Helper method to create/update a single quota"""
        from datetime import datetime
        from .models import ComplianceQuota
        
        law = quota_data.get('law')
        year = int(quota_data.get('year'))
        target = int(quota_data.get('target'))
        
        # Support both month and quarter (month takes precedence)
        month = quota_data.get('month')
        quarter = quota_data.get('quarter')
        
        if not law or not target:
            raise ValueError('Law and target are required')
        
        # Validate law code against Law model
        valid_laws = ComplianceQuota.get_active_laws()
        if not valid_laws:
            raise ValueError('No active laws found. Please add laws to the Law Management system first.')
        if law not in valid_laws:
            raise ValueError(f'Invalid law code. Must be one of: {", ".join(valid_laws)}')
        
        # Month is required for monthly quotas
        if not month:
            raise ValueError('Month is required for quota creation')
        
        month = int(month)
        if month < 1 or month > 12:
            raise ValueError('Month must be between 1 and 12')
        
        # Derive quarter from month
        quarter = ComplianceQuota.get_quarter_from_month(month)
        
        # Validate that month is not in the past
        current_year = datetime.now().year
        current_month = datetime.now().month
        if year < current_year or (year == current_year and month < current_month):
            raise ValueError('Cannot create or edit quotas for past months')
        
        # Validate target
        if target <= 0:
            raise ValueError('Target must be greater than 0')
        
        # Check for duplicate (same law + year + month)
        existing_quota = ComplianceQuota.objects.filter(
            law=law,
            year=year,
            month=month
        ).first()
        
        # Check if updating existing quota by ID
        quota_id = quota_data.get('id')
        if quota_id:
            try:
                quota = ComplianceQuota.objects.get(id=quota_id)
                quota.target = target
                quota.month = month  # Ensure month is set
                quota.quarter = quarter  # Update quarter from month
                quota.created_by = user
                quota.auto_adjusted = False
                quota.save()
                created = False
            except ComplianceQuota.DoesNotExist:
                raise ValueError('Quota with provided ID does not exist')
        else:
            # Check for duplicate (same law + year + month)
            if existing_quota:
                month_names = ['January', 'February', 'March', 'April', 'May', 'June', 
                              'July', 'August', 'September', 'October', 'November', 'December']
                raise ValueError(f'Quota for {month_names[month-1]} {year} already exists')
            
            quota, created = ComplianceQuota.objects.update_or_create(
                law=law,
                year=year,
                month=month,  # Use month for unique constraint
                defaults={
                    'quarter': quarter,  # Store quarter for reference
                    'target': target,
                    'created_by': user,
                    'auto_adjusted': False  # Manual setting overrides auto-adjustment
                }
            )
        
        # Use the actual month from the quota
        month_value = quota.month
        
        return {
            'id': quota.id,
            'law': quota.law,
            'year': quota.year,
            'quarter': quota.quarter,
            'month': quota.month,  # Return actual month
            'target': quota.target,
            'accomplished': quota.accomplished,
            'auto_adjusted': quota.auto_adjusted,
            'percentage': quota.percentage,
            'exceeded': quota.exceeded,
            'created': created,
            'message': 'Quota created successfully' if created else 'Quota updated successfully'
        }

    @action(detail=False, methods=['post'])
    def auto_adjust_quotas(self, request):
        """Auto-adjust next quarter quotas based on current accomplishments"""
        from datetime import datetime
        from .models import ComplianceQuota
        
        year = int(request.data.get('year', datetime.now().year))
        quarter = int(request.data.get('quarter', ((datetime.now().month - 1) // 3) + 1))
        
        current_quotas = ComplianceQuota.objects.filter(year=year, quarter=quarter)
        adjusted_quotas = []
        
        for quota in current_quotas:
            if quota.accomplished > quota.target:
                next_quota = quota.auto_adjust_next_quarter()
                if next_quota:
                    adjusted_quotas.append({
                        'law': quota.law,
                        'current_quarter': f"Q{quota.quarter} {quota.year}",
                        'accomplished': quota.accomplished,
                        'next_quarter': f"Q{next_quota.quarter} {next_quota.year}",
                        'new_target': next_quota.target,
                        'auto_adjusted': next_quota.auto_adjusted
                    })
        
        return Response({
            'adjusted_quotas': adjusted_quotas,
            'message': f"Auto-adjusted {len(adjusted_quotas)} quotas for next quarter",
            'total_adjusted': len(adjusted_quotas)
        })
    
    @action(detail=False, methods=['get'], url_path='quota-laws')
    def get_quota_laws(self, request):
        """Get list of active laws for quota management"""
        from .models import ComplianceQuota
        from laws.models import Law
        
        # Get all active laws
        active_laws = Law.objects.filter(status='Active').order_by('reference_code')
        
        laws_data = []
        for law in active_laws:
            laws_data.append({
                'id': law.reference_code,
                'reference_code': law.reference_code,
                'name': f"{law.reference_code} ({law.category})",
                'fullName': law.law_title,
                'law_title': law.law_title,
                'category': law.category,
                'effective_date': law.effective_date.isoformat() if law.effective_date else None,
                'status': law.status
            })
        
        return Response(laws_data)

    @action(detail=False, methods=['post'])
    def evaluate_quarter(self, request):
        """Evaluate a quarter: calculate totals, determine status, create/update evaluation"""
        from datetime import datetime
        from .models import ComplianceQuota, QuarterlyEvaluation
        
        law = request.data.get('law')
        year = int(request.data.get('year'))
        quarter = int(request.data.get('quarter'))
        remarks = request.data.get('remarks', '')
        
        # Validate inputs
        if not law or not year or not quarter:
            return Response(
                {'error': 'Law, year, and quarter are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if quarter not in [1, 2, 3, 4]:
            return Response(
                {'error': 'Quarter must be 1, 2, 3, or 4'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Calculate quarterly totals
        total_target, total_achieved = ComplianceQuota.get_quarterly_totals(law, year, quarter)
        
        # Determine status
        if total_achieved >= total_target:
            quarter_status = 'EXCEEDED' if total_achieved > total_target else 'ACHIEVED'
        else:
            quarter_status = 'NOT_ACHIEVED'
        
        # Calculate surplus/deficit
        surplus = max(0, total_achieved - total_target)
        deficit = max(0, total_target - total_achieved)
        
        # Create or update evaluation
        evaluation, created = QuarterlyEvaluation.objects.update_or_create(
            law=law,
            year=year,
            quarter=quarter,
            defaults={
                'quarterly_target': total_target,
                'quarterly_achieved': total_achieved,
                'quarter_status': quarter_status,
                'surplus': surplus,
                'deficit': deficit,
                'remarks': remarks,
                'evaluated_by': request.user,
                'is_archived': True
            }
        )
        
        # Apply carry-over if enabled and policy is auto
        carry_over_applied = False
        if deficit > 0:
            # Carry-over is now disabled (was previously in system_config)
            # For future implementation, add carry_over settings to .env
            carry_over_applied = False
            carry_over_applied = True
        
        return Response({
            'id': evaluation.id,
            'law': evaluation.law,
            'year': evaluation.year,
            'quarter': evaluation.quarter,
            'quarterly_target': evaluation.quarterly_target,
            'quarterly_achieved': evaluation.quarterly_achieved,
            'quarter_status': evaluation.quarter_status,
            'surplus': evaluation.surplus,
            'deficit': evaluation.deficit,
            'percentage': evaluation.percentage,
            'remarks': evaluation.remarks,
            'evaluated_at': evaluation.evaluated_at,
            'evaluated_by': evaluation.evaluated_by.email if evaluation.evaluated_by else None,
            'is_archived': evaluation.is_archived,
            'created': created,
            'carry_over_applied': carry_over_applied,
            'message': 'Quarter evaluated successfully'
        })

    @action(detail=False, methods=['get'])
    def get_quarterly_evaluations(self, request):
        """Get all evaluated quarters (archived)"""
        from .models import QuarterlyEvaluation
        
        year = request.query_params.get('year')
        quarter = request.query_params.get('quarter')
        law = request.query_params.get('law')
        
        evaluations = QuarterlyEvaluation.objects.all()
        
        if year:
            evaluations = evaluations.filter(year=int(year))
        if quarter:
            evaluations = evaluations.filter(quarter=int(quarter))
        if law:
            evaluations = evaluations.filter(law=law)
        
        # Apply role-based filtering
        user = request.user
        if user.userlevel == 'Section Chief':
            if hasattr(user, 'section') and user.section:
                if user.section == 'PD-1586,RA-8749,RA-9275':
                    evaluations = evaluations.filter(law__in=['PD-1586', 'RA-8749', 'RA-9275'])
                else:
                    evaluations = evaluations.filter(law=user.section)
        elif user.userlevel == 'Unit Head':
            if hasattr(user, 'section') and user.section:
                evaluations = evaluations.filter(law=user.section)
        
        evaluation_data = []
        for eval in evaluations:
            evaluation_data.append({
                'id': eval.id,
                'law': eval.law,
                'year': eval.year,
                'quarter': eval.quarter,
                'quarterly_target': eval.quarterly_target,
                'quarterly_achieved': eval.quarterly_achieved,
                'quarter_status': eval.quarter_status,
                'surplus': eval.surplus,
                'deficit': eval.deficit,
                'percentage': eval.percentage,
                'remarks': eval.remarks,
                'evaluated_at': eval.evaluated_at,
                'evaluated_by': eval.evaluated_by.email if eval.evaluated_by else None,
                'is_archived': eval.is_archived
            })
        
        return Response(evaluation_data)

    @action(detail=False, methods=['post'])
    def manual_evaluate_quarter(self, request):
        """Manually trigger quarter evaluation (admin only)"""
        # This is essentially the same as evaluate_quarter, but with validation
        # that the quarter has ended (or allow override for current quarter)
        from datetime import datetime
        
        current_date = datetime.now()
        current_year = current_date.year
        current_quarter = ((current_date.month - 1) // 3) + 1
        
        year = int(request.data.get('year'))
        quarter = int(request.data.get('quarter'))
        
        # Allow evaluation of current or past quarters
        if year > current_year or (year == current_year and quarter > current_quarter):
            return Response(
                {'error': 'Cannot evaluate future quarters'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Use the same evaluation logic
        return self.evaluate_quarter(request)

    @action(detail=False, methods=['post'])
    def apply_carry_over(self, request):
        """Apply carry-over from evaluated quarter to next quarter"""
        from .models import QuarterlyEvaluation, ComplianceQuota
        
        evaluation_id = request.data.get('evaluation_id')
        if not evaluation_id:
            return Response(
                {'error': 'Evaluation ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            evaluation = QuarterlyEvaluation.objects.get(id=evaluation_id)
        except QuarterlyEvaluation.DoesNotExist:
            return Response(
                {'error': 'Evaluation not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        config = SystemConfiguration.get_active_config()
        if not config.quota_carry_over_enabled:
            return Response(
                {'error': 'Carry-over is not enabled in system settings'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if evaluation.deficit <= 0:
            return Response(
                {'error': 'No deficit to carry over'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Calculate next quarter
        next_quarter = evaluation.quarter + 1 if evaluation.quarter < 4 else 1
        next_year = evaluation.year if evaluation.quarter < 4 else evaluation.year + 1
        
        # For now, apply to quarterly quota (will update when monthly structure is in place)
        next_quota, created = ComplianceQuota.objects.get_or_create(
            law=evaluation.law,
            year=next_year,
            quarter=next_quarter,
            defaults={
                'target': evaluation.deficit,  # Add deficit to target
                'created_by': request.user,
                'auto_adjusted': True
            }
        )
        
        if not created:
            next_quota.target += evaluation.deficit
            next_quota.auto_adjusted = True
            next_quota.save()
        
        return Response({
            'message': f'Carry-over applied: {evaluation.deficit} added to Q{next_quarter} {next_year}',
            'next_quota': {
                'id': next_quota.id,
                'law': next_quota.law,
                'year': next_quota.year,
                'quarter': next_quota.quarter,
                'target': next_quota.target
            }
        })

    @action(detail=False, methods=['get'], url_path='yearly-summary')
    def get_yearly_summary(self, request):
        """Get yearly summary of all quarters"""
        from datetime import datetime
        from .models import QuarterlyEvaluation
        
        year = int(request.query_params.get('year', datetime.now().year))
        
        evaluations = QuarterlyEvaluation.objects.filter(year=year).order_by('quarter', 'law')
        
        # Aggregate by law
        summary = {}
        for eval in evaluations:
            if eval.law not in summary:
                summary[eval.law] = {
                    'law': eval.law,
                    'year': year,
                    'total_target': 0,
                    'total_achieved': 0,
                    'total_surplus': 0,
                    'total_deficit': 0,
                    'quarters': []
                }
            
            summary[eval.law]['total_target'] += eval.quarterly_target
            summary[eval.law]['total_achieved'] += eval.quarterly_achieved
            summary[eval.law]['total_surplus'] += eval.surplus
            summary[eval.law]['total_deficit'] += eval.deficit
            summary[eval.law]['quarters'].append({
                'quarter': eval.quarter,
                'target': eval.quarterly_target,
                'achieved': eval.quarterly_achieved,
                'status': eval.quarter_status,
                'percentage': eval.percentage
            })
        
        # Calculate overall percentages
        for law_data in summary.values():
            if law_data['total_target'] > 0:
                law_data['overall_percentage'] = round(
                    (law_data['total_achieved'] / law_data['total_target']) * 100, 1
                )
            else:
                law_data['overall_percentage'] = 0
        
        return Response(list(summary.values()))

    @action(detail=False, methods=['get'], url_path='reinspection-reminders')
    def reinspection_reminders(self, request):
        """Get all reinspection schedules for Division Chiefs"""
        from django.utils import timezone
        from datetime import timedelta
        from .models import ReinspectionSchedule
        
        # Only allow Division Chiefs
        if request.user.userlevel != 'Division Chief':
            return Response(
                {'error': 'Access denied. Only Division Chiefs can view reinspection reminders.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get all reinspection schedules (not just upcoming ones)
        schedules = ReinspectionSchedule.objects.filter(
            status='PENDING'
        ).select_related('establishment', 'original_inspection')
        
        reminders = []
        today = timezone.now().date()
        
        for schedule in schedules:
            days_until_due = (schedule.due_date - today).days
            
            # Construct address manually since get_full_address doesn't exist
            establishment = schedule.establishment
            address_parts = [
                establishment.street_building,
                establishment.barangay,
                establishment.city,
                establishment.province
            ]
            full_address = ', '.join(filter(None, address_parts))
            
            reminders.append({
                'id': schedule.id,
                'establishment_name': establishment.name,
                'establishment_address': full_address,
                'original_inspection_code': schedule.original_inspection.code,
                'compliance_status': schedule.compliance_status,
                'due_date': schedule.due_date,
                'days_until_due': days_until_due,
                'is_overdue': days_until_due < 0
            })
        
        return Response(reminders)

    @action(detail=True, methods=['post'], url_path='upload_signature', permission_classes=[permissions.IsAuthenticated])
    def upload_signature(self, request, pk=None):
        """
        Upload signature image for current user's review stage
        """
        import uuid
        import os
        from django.core.files.storage import default_storage
        from django.utils import timezone
        
        inspection = self.get_object()
        form = getattr(inspection, 'form', None)
        
        if not form:
            return Response(
                {'detail': 'Inspection form not found.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = SignatureUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Validate user has permission to upload to this slot
        slot = serializer.validated_data['slot']
        user_level = request.user.userlevel
        inspector_level = form.inspected_by.userlevel if form.inspected_by else None
        is_original_inspector = form.inspected_by and form.inspected_by.id == request.user.id
        
        # Role-based slot validation
        allowed = False
        
        # Allow original inspector to upload their own 'submitted' signature regardless of level
        if slot == 'submitted' and is_original_inspector:
            allowed = True
        # Allow user to upload 'submitted' signature if inspector hasn't been set yet (preview mode)
        elif slot == 'submitted' and form.inspected_by is None:
            allowed = True
        elif inspector_level == 'Monitoring Personnel':
            if slot == 'submitted' and user_level == 'Monitoring Personnel':
                allowed = True
            elif slot == 'review_unit' and user_level == 'Unit Head':
                allowed = True
            elif slot == 'review_section' and user_level == 'Section Chief':
                allowed = True
            elif slot == 'approve_division' and user_level == 'Division Chief':
                allowed = True
        elif inspector_level == 'Unit Head':
            if slot == 'submitted' and user_level == 'Unit Head':
                allowed = True
            elif slot == 'review_section' and user_level == 'Section Chief':
                allowed = True
            elif slot == 'approve_division' and user_level == 'Division Chief':
                allowed = True
        elif inspector_level == 'Section Chief':
            if slot in ['submitted', 'review_section'] and user_level == 'Section Chief':
                allowed = True
            elif slot == 'approve_division' and user_level == 'Division Chief':
                allowed = True
        
        if not allowed:
            # Provide detailed error for debugging
            error_detail = (
                f'You do not have permission to upload signature for slot "{slot}". '
                f'User level: {user_level}, Inspector level: {inspector_level}, '
                f'Is original inspector: {is_original_inspector}, Inspector ID: {form.inspected_by.id if form.inspected_by else None}, User ID: {request.user.id}'
            )
            logger.warning(f'Signature upload denied: {error_detail}')
            return Response(
                {'detail': error_detail},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Save signature
        file = serializer.validated_data['file']
        checklist = form.checklist or {}
        signatures = checklist.get('signatures', {})
        
        # Save file to media storage
        file_ext = os.path.splitext(file.name)[1].lower()
        file_name = f'signatures/{inspection.code}/{slot}_{uuid.uuid4()}{file_ext}'
        path = default_storage.save(file_name, file)
        relative_url = default_storage.url(path)
        
        # Convert to absolute URL if it's relative
        if relative_url.startswith('/'):
            url = request.build_absolute_uri(relative_url)
        else:
            url = relative_url
        
        # Store signature metadata
        signatures[slot] = {
            'url': url,
            'uploaded_by': request.user.id,
            'uploaded_at': timezone.now().isoformat(),
            'name': f"{request.user.first_name} {request.user.last_name}".strip() or request.user.email,
            'title': request.user.userlevel,
        }
        
        checklist['signatures'] = signatures
        form.checklist = checklist
        form.save(update_fields=['checklist'])
        
        # Audit log
        audit_inspection_event(
            request.user,
            inspection,
            AUDIT_ACTIONS["UPDATE"],
            f"Signature uploaded for {slot} by {request.user.email}",
            request,
            metadata={'slot': slot}
        )
        
        return Response({
            'detail': 'Signature uploaded successfully.',
            'slot': slot
        })

    @action(detail=True, methods=['delete'], url_path='delete_signature', permission_classes=[permissions.IsAuthenticated])
    def delete_signature(self, request, pk=None):
        """
        Delete signature image (only own signature or admin)
        """
        from django.core.files.storage import default_storage
        
        inspection = self.get_object()
        form = getattr(inspection, 'form', None)
        
        if not form:
            return Response(
                {'detail': 'Inspection form not found.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        slot = request.data.get('slot')
        if not slot:
            return Response(
                {'detail': 'Slot parameter is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        checklist = form.checklist or {}
        signatures = checklist.get('signatures', {})
        
        if slot not in signatures:
            return Response(
                {'detail': 'Signature not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permission (only uploader or admin can delete)
        signature_data = signatures[slot]
        if signature_data.get('uploaded_by') != request.user.id and request.user.userlevel != 'Admin':
            return Response(
                {'detail': 'You do not have permission to delete this signature.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Delete file from storage
        url = signature_data.get('url', '')
        if url:
            # Extract path from URL
            path = url.replace(default_storage.base_url, '')
            if default_storage.exists(path):
                default_storage.delete(path)
        
        # Remove from checklist
        del signatures[slot]
        checklist['signatures'] = signatures
        form.checklist = checklist
        form.save(update_fields=['checklist'])
        
        return Response({'detail': 'Signature deleted successfully.'})

    @action(detail=True, methods=['get'], url_path='previous-violations', permission_classes=[permissions.IsAuthenticated])
    def previous_violations(self, request, pk=None):
        """
        Get previous violations from the most recent closed inspection for establishments in this inspection
        """
        inspection = self.get_object()
        establishments = inspection.establishments.all()
        
        previous_violations_data = []
        
        for establishment in establishments:
            # Find the most recent closed inspection for this establishment
            # Check both by direct link (if this is a reinspection) and by establishment history
            previous_inspection = None
            
            # First, check if this inspection has a previous_inspection link
            if inspection.previous_inspection and establishment in inspection.previous_inspection.establishments.all():
                previous_inspection = inspection.previous_inspection
            else:
                # Find most recent closed inspection for this establishment
                from .models import InspectionForm
                recent_inspections = Inspection.objects.filter(
                    establishments=establishment,
                    current_status__in=['CLOSED_COMPLIANT', 'CLOSED_NON_COMPLIANT']
                ).exclude(id=inspection.id).order_by('-updated_at')
                
                if recent_inspections.exists():
                    previous_inspection = recent_inspections.first()
            
            if previous_inspection:
                form = getattr(previous_inspection, 'form', None)
                violations_found = form.violations_found if form and form.violations_found else None
                
                if violations_found:
                    previous_violations_data.append({
                        'establishment_id': establishment.id,
                        'establishment_name': establishment.name,
                        'previous_inspection_code': previous_inspection.code,
                        'previous_inspection_date': previous_inspection.created_at.isoformat() if previous_inspection.created_at else None,
                        'compliance_status': previous_inspection.current_status,
                        'violations': violations_found
                    })
        
        return Response({
            'previous_violations': previous_violations_data,
            'has_previous_violations': len(previous_violations_data) > 0
        })

    @action(detail=True, methods=['post'], url_path='add_recommendation')
    def add_recommendation(self, request, pk=None):
        """Add a recommendation to inspection"""
        import uuid
        from django.utils import timezone
        
        inspection = self.get_object()
        form = getattr(inspection, 'form', None)
        
        if not form:
            return Response({'detail': 'Inspection form not found.'}, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = RecommendationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        checklist = form.checklist or {}
        recommendations = checklist.get('recommendations', [])
        
        new_rec = {
            'id': str(uuid.uuid4()),
            'text': serializer.validated_data['text'],
            'priority': serializer.validated_data.get('priority', 'MEDIUM'),
            'category': serializer.validated_data.get('category', 'COMPLIANCE'),
            'status': serializer.validated_data.get('status', 'PENDING'),
            'created_by': request.user.id,
            'created_by_name': f"{request.user.first_name} {request.user.last_name}".strip() or request.user.email,
            'created_at': timezone.now().isoformat(),
        }
        
        recommendations.append(new_rec)
        checklist['recommendations'] = recommendations
        form.checklist = checklist
        form.save(update_fields=['checklist'])
        
        # Audit log
        audit_inspection_event(
            request.user,
            inspection,
            AUDIT_ACTIONS["UPDATE"],
            f"Recommendation added by {request.user.email}",
            request,
            metadata={'recommendation_id': new_rec['id']}
        )
        
        return Response(new_rec, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['put'], url_path='update_recommendation/(?P<rec_id>[^/.]+)')
    def update_recommendation(self, request, pk=None, rec_id=None):
        """Update a recommendation"""
        inspection = self.get_object()
        form = getattr(inspection, 'form', None)
        
        if not form:
            return Response({'detail': 'Inspection form not found.'}, status=status.HTTP_400_BAD_REQUEST)
        
        checklist = form.checklist or {}
        recommendations = checklist.get('recommendations', [])
        
        # Find recommendation
        rec_index = next((i for i, r in enumerate(recommendations) if r.get('id') == rec_id), None)
        if rec_index is None:
            return Response({'detail': 'Recommendation not found.'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = RecommendationSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        # Update recommendation
        recommendation = recommendations[rec_index]
        if 'text' in serializer.validated_data:
            recommendation['text'] = serializer.validated_data['text']
        if 'priority' in serializer.validated_data:
            recommendation['priority'] = serializer.validated_data['priority']
        if 'category' in serializer.validated_data:
            recommendation['category'] = serializer.validated_data['category']
        if 'status' in serializer.validated_data:
            recommendation['status'] = serializer.validated_data['status']
        
        recommendations[rec_index] = recommendation
        checklist['recommendations'] = recommendations
        form.checklist = checklist
        form.save(update_fields=['checklist'])
        
        return Response(recommendation)

    @action(detail=True, methods=['delete'], url_path='delete_recommendation/(?P<rec_id>[^/.]+)')
    def delete_recommendation(self, request, pk=None, rec_id=None):
        """Delete a recommendation"""
        inspection = self.get_object()
        form = getattr(inspection, 'form', None)
        
        if not form:
            return Response({'detail': 'Inspection form not found.'}, status=status.HTTP_400_BAD_REQUEST)
        
        checklist = form.checklist or {}
        recommendations = checklist.get('recommendations', [])
        
        # Find and remove recommendation
        rec_index = next((i for i, r in enumerate(recommendations) if r.get('id') == rec_id), None)
        if rec_index is None:
            return Response({'detail': 'Recommendation not found.'}, status=status.HTTP_404_NOT_FOUND)
        
        recommendations.pop(rec_index)
        checklist['recommendations'] = recommendations
        form.checklist = checklist
        form.save(update_fields=['checklist'])
        
        return Response({'detail': 'Recommendation deleted successfully.'})


class BillingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Billing Records
    """
    queryset = BillingRecord.objects.all().order_by('-created_at')
    serializer_class = BillingRecordSerializer
    permission_classes = [permissions.IsAuthenticated]

    @staticmethod
    def _serialize_payment_state(billing):
        return {
            "payment_status": billing.payment_status,
            "payment_date": billing.payment_date.isoformat() if billing.payment_date else None,
            "payment_reference": billing.payment_reference or "",
            "payment_notes": billing.payment_notes or "",
        }
    
    def get_queryset(self):
        """Filter billing records based on user level and permissions"""
        user = self.request.user
        queryset = BillingRecord.objects.all()
        
        # Legal Unit can see all billing records
        if user.userlevel == 'Legal Unit':
            pass  # No filter, see all
        # Division/Section Chiefs can see all
        elif user.userlevel in ['Division Chief', 'Section Chief']:
            pass  # No filter, see all
        # Others can only see their related law
        elif hasattr(user, 'law') and user.law:
            queryset = queryset.filter(related_law=user.law)
        else:
            # No access for others
            queryset = queryset.none()
        
        # Apply filters from query params
        law = self.request.query_params.get('law', None)
        if law:
            # Normalize law format - try multiple formats
            law_normalized = law.replace(' ', '').replace('-', '')
            # Try to add dashes if it's a law code like RA8749 -> RA-8749
            if law.startswith('RA') and len(law) > 2:
                law_with_dash = f"RA-{law[2:]}"
                law_with_spaces = f"RA {law[2:]}"
            elif law.startswith('PD') and len(law) > 2:
                law_with_dash = f"PD-{law[2:]}"
                law_with_spaces = f"PD {law[2:]}"
            else:
                law_with_dash = law
                law_with_spaces = law
            
            queryset = queryset.filter(
                Q(related_law=law) | 
                Q(related_law=law_normalized) |
                Q(related_law=law_with_dash) |
                Q(related_law=law_with_spaces) |
                Q(related_law__icontains=law.replace(' ', '').replace('-', ''))
            )
        
        establishment_id = self.request.query_params.get('establishment', None)
        if establishment_id:
            queryset = queryset.filter(establishment_id=establishment_id)
        
        # Filter by inspection id (used by InspectionView billing panel)
        inspection_id = self.request.query_params.get('inspection', None)
        if inspection_id:
            queryset = queryset.filter(inspection_id=inspection_id)
        
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(billing_code__icontains=search) |
                Q(establishment_name__icontains=search) |
                Q(description__icontains=search)
            )
        
        return queryset.select_related('inspection', 'establishment', 'issued_by')
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get billing statistics"""
        from django.db.models import Sum, Count, Avg
        
        queryset = self.get_queryset()
        
        stats = {
            'total_records': queryset.count(),
            'total_amount': queryset.aggregate(Sum('amount'))['amount__sum'] or 0,
            'average_amount': queryset.aggregate(Avg('amount'))['amount__avg'] or 0,
            'by_type': [],
            'by_law': []
        }
        
        # Stats by billing type
        type_stats = queryset.values('billing_type').annotate(
            count=Count('id'),
            total=Sum('amount')
        ).order_by('-count')
        
        for item in type_stats:
            stats['by_type'].append({
                'type': item['billing_type'],
                'count': item['count'],
                'total': float(item['total'] or 0)
            })
        
        # Stats by law
        law_stats = queryset.values('related_law').annotate(
            count=Count('id'),
            total=Sum('amount')
        ).order_by('-count')
        
        for item in law_stats:
            stats['by_law'].append({
                'law': item['related_law'],
                'count': item['count'],
                'total': float(item['total'] or 0)
            })
        
        return Response(stats)
    
    @action(detail=True, methods=['post'], url_path='mark-paid')
    def mark_paid(self, request, pk=None):
        """Tag a billing record as paid"""
        billing = self.get_object()
        before_state = self._serialize_payment_state(billing)
        
        payload = {
            'payment_status': 'PAID',
            'payment_date': request.data.get('payment_date'),
            'payment_reference': request.data.get('payment_reference', ''),
            'payment_notes': request.data.get('payment_notes', '')
        }
        
        serializer = self.get_serializer(billing, data=payload, partial=True)
        serializer.is_valid(raise_exception=True)
        
        validated = serializer.validated_data
        payment_date = validated.get('payment_date') or timezone.now().date()
        billing.payment_status = 'PAID'
        billing.payment_date = payment_date
        billing.payment_reference = validated.get('payment_reference', '')
        billing.payment_notes = validated.get('payment_notes', '')
        billing.payment_confirmed_by = request.user
        billing.payment_confirmed_at = timezone.now()
        billing.save()

        after_state = self._serialize_payment_state(billing)

        log_activity(
            request.user,
            AUDIT_ACTIONS["UPDATE"],
            module="BILLING",
            description=f"Marked billing {billing.billing_code} as paid",
            metadata={
                "entity_id": billing.id,
                "entity_name": billing.billing_code,
                "entity_type": "billing",
                "status": "success",
            },
            before=before_state,
            after=after_state,
            request=request,
        )
        
        return Response(self.get_serializer(billing).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='mark-unpaid')
    def mark_unpaid(self, request, pk=None):
        """Revert a billing record back to unpaid status"""
        billing = self.get_object()
        before_state = self._serialize_payment_state(billing)
        payment_notes = request.data.get('payment_notes', '').strip()

        if not payment_notes:
            return Response(
                {"detail": "A remark is required when reverting to unpaid."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = self.get_serializer(
            billing,
            data={'payment_notes': payment_notes},
            partial=True
        )
        serializer.is_valid(raise_exception=True)

        billing.payment_status = 'UNPAID'
        billing.payment_date = None
        billing.payment_reference = ''
        billing.payment_notes = serializer.validated_data.get('payment_notes', '')
        billing.payment_confirmed_by = None
        billing.payment_confirmed_at = None
        billing.save()

        after_state = self._serialize_payment_state(billing)

        log_activity(
            request.user,
            AUDIT_ACTIONS["UPDATE"],
            module="BILLING",
            description=f"Reverted billing {billing.billing_code} to unpaid",
            metadata={
                "entity_id": billing.id,
                "entity_name": billing.billing_code,
                "entity_type": "billing",
                "status": "success",
            },
            before=before_state,
            after=after_state,
            request=request,
        )

        return Response(self.get_serializer(billing).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='audit-logs')
    def audit_logs(self, request, pk=None):
        """Return audit history for a billing record"""
        billing = self.get_object()
        module_label = AUDIT_MODULES.get("BILLING", "Billing & Payments")
        logs = ActivityLog.objects.filter(
            Q(metadata__entity_id=billing.id) | Q(metadata__entity_id=str(billing.id)),
            metadata__entity_type='billing',
            module=module_label
        ).order_by('-created_at')[:50]
        serializer = ActivityLogSerializer(logs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def print_receipt(self, request, pk=None):
        """Generate printable billing receipt"""
        billing = self.get_object()
        serializer = self.get_serializer(billing)
        
        # Return formatted data for printing
        return Response({
            'billing': serializer.data,
            'generated_at': timezone.now().isoformat()
        })


class LegalReportViewSet(viewsets.ViewSet):
    """
    ViewSet for Legal Unit Report Generation
    Provides comprehensive reporting with filtering, statistics, and export capabilities
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def _get_base_queryset(self, request):
        """Get base queryset with filters applied"""
        from django.db.models import Q
        
        queryset = BillingRecord.objects.all()
        
        # Access control - Legal Unit can see all
        user = request.user
        if user.userlevel != 'Legal Unit' and user.userlevel not in ['Division Chief', 'Section Chief', 'Admin']:
            # Others can only see their related law
            if hasattr(user, 'law') and user.law:
                queryset = queryset.filter(related_law=user.law)
            else:
                queryset = queryset.none()
        
        # Date filters
        billing_date_from = request.query_params.get('billing_date_from')
        billing_date_to = request.query_params.get('billing_date_to')
        if billing_date_from:
            queryset = queryset.filter(sent_date__gte=billing_date_from)
        if billing_date_to:
            queryset = queryset.filter(sent_date__lte=billing_date_to)
        
        # Establishment filter
        establishment = request.query_params.get('establishment')
        if establishment:
            queryset = queryset.filter(
                Q(establishment_name__icontains=establishment) |
                Q(establishment_id=establishment)
            )
        
        # Inspection control number
        inspection_code = request.query_params.get('inspection_code')
        if inspection_code:
            queryset = queryset.filter(inspection__code__icontains=inspection_code)
        
        # Billing status
        payment_status = request.query_params.get('payment_status')
        if payment_status and payment_status != 'ALL':
            queryset = queryset.filter(payment_status=payment_status)
        
        # Legal action filter
        legal_action = request.query_params.get('legal_action')
        if legal_action and legal_action != 'ALL':
            queryset = queryset.filter(legal_action=legal_action)
        
        # Law filter
        law = request.query_params.get('law')
        if law and law != 'ALL':
            queryset = queryset.filter(related_law__icontains=law.replace('-', ''))
        
        # Compliance status filter (requires join with inspection form)
        compliance_status = request.query_params.get('compliance_status')
        if compliance_status and compliance_status != 'ALL':
            # Handle cases where form might not exist - treat missing forms as PENDING
            if compliance_status == 'PENDING':
                queryset = queryset.filter(
                    Q(inspection__form__compliance_decision__isnull=True) |
                    Q(inspection__form__compliance_decision='PENDING') |
                    Q(inspection__form__isnull=True)
                )
            else:
                queryset = queryset.filter(inspection__form__compliance_decision=compliance_status)
        
        # NOV/NOO filter
        has_nov = request.query_params.get('has_nov')
        if has_nov == 'true':
            queryset = queryset.filter(inspection__form__nov__isnull=False)
        elif has_nov == 'false':
            queryset = queryset.filter(inspection__form__nov__isnull=True)
        
        has_noo = request.query_params.get('has_noo')
        if has_noo == 'true':
            queryset = queryset.filter(inspection__form__noo__isnull=False)
        elif has_noo == 'false':
            queryset = queryset.filter(inspection__form__noo__isnull=True)
        
        # Optimize queries - use prefetch for form to handle cases where form might not exist
        queryset = queryset.select_related(
            'inspection',
            'establishment',
            'issued_by'
        ).prefetch_related(
            'inspection__form',
            'inspection__form__nov',
            'inspection__form__noo'
        )
        
        return queryset
    
    def list(self, request):
        """Get filtered billing records for report"""
        from core.pagination import StandardResultsSetPagination
        import logging
        
        logger = logging.getLogger(__name__)
        
        queryset = self._get_base_queryset(request)
        queryset = queryset.order_by('-created_at')
        
        # Log query info for debugging
        total_count = queryset.count()
        logger.info(f"Legal Report Query - Total records before pagination: {total_count}")
        logger.info(f"Legal Report Query - Filters: {dict(request.query_params)}")
        
        # Pagination
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = LegalReportSerializer(page, many=True)
            response_data = paginator.get_paginated_response(serializer.data)
            logger.info(f"Legal Report Query - Returning {len(serializer.data)} records (paginated)")
            return response_data
        
        serializer = LegalReportSerializer(queryset, many=True)
        logger.info(f"Legal Report Query - Returning {len(serializer.data)} records (non-paginated)")
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get computed summary statistics"""
        from django.db.models import Sum, Avg, Count, Q, F
        from datetime import timedelta
        
        queryset = self._get_base_queryset(request)
        
        # Billing summary
        billing_aggregates = queryset.aggregate(
            total_billed=Sum('amount'),
            total_paid=Sum('amount', filter=Q(payment_status='PAID')),
            avg_days_to_payment=Avg(
                F('payment_date') - F('sent_date'),
                filter=Q(payment_status='PAID', payment_date__isnull=False)
            )
        )
        
        total_billed = billing_aggregates['total_billed'] or 0
        total_paid = billing_aggregates['total_paid'] or 0
        outstanding_balance = total_billed - total_paid
        
        avg_days = billing_aggregates['avg_days_to_payment']
        avg_days_to_payment = avg_days.days if avg_days else 0
        
        # Count NOV/NOO
        total_nov = queryset.filter(inspection__form__nov__isnull=False).count()
        total_noo = queryset.filter(inspection__form__noo__isnull=False).count()
        
        # Compliance summary
        compliant_count = queryset.filter(
            inspection__form__compliance_decision='COMPLIANT'
        ).count()
        non_compliant_count = queryset.filter(
            inspection__form__compliance_decision='NON_COMPLIANT'
        ).count()
        pending_count = queryset.filter(
            Q(inspection__form__compliance_decision__isnull=True) |
            Q(inspection__form__compliance_decision='PENDING')
        ).count()
        
        # Re-inspections recommended (non-compliant with no payment)
        reinspection_recommended = queryset.filter(
            inspection__form__compliance_decision='NON_COMPLIANT',
            payment_status='UNPAID'
        ).count()
        
        return Response({
            'billing_summary': {
                'total_billed': float(total_billed),
                'total_paid': float(total_paid),
                'outstanding_balance': float(outstanding_balance),
                'avg_days_to_payment': avg_days_to_payment,
                'total_nov': total_nov,
                'total_noo': total_noo,
            },
            'compliance_summary': {
                'compliant_count': compliant_count,
                'non_compliant_count': non_compliant_count,
                'pending_count': pending_count,
                'reinspection_recommended': reinspection_recommended,
            }
        })
    
    @action(detail=False, methods=['get'])
    def recommendations(self, request):
        """Generate system-based recommendations"""
        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import Count
        
        queryset = self._get_base_queryset(request)
        recommendations = []
        
        # Repeated non-compliance (establishments with 2+ non-compliant inspections)
        repeated_non_compliant = queryset.filter(
            inspection__form__compliance_decision='NON_COMPLIANT'
        ).values('establishment_id', 'establishment_name').annotate(
            count=Count('id')
        ).filter(count__gte=2)
        
        if repeated_non_compliant.exists():
            establishments = [est['establishment_name'] for est in repeated_non_compliant[:5]]
            recommendations.append({
                'type': 'Repeated Non-Compliance',
                'description': f"The following establishments have repeated non-compliance issues: {', '.join(establishments)}. Consider escalating legal action."
            })
        
        # Overdue payments (30+ days)
        today = timezone.now().date()
        overdue_threshold = today - timedelta(days=30)
        overdue_payments = queryset.filter(
            payment_status='UNPAID',
            due_date__lt=overdue_threshold
        )
        
        if overdue_payments.exists():
            recommendations.append({
                'type': 'Overdue Payments',
                'description': f"{overdue_payments.count()} establishments have payments overdue for more than 30 days. Immediate follow-up and potential legal escalation required."
            })
        
        # Legal escalation needed (non-compliant + no payment + no legal action)
        needs_escalation = queryset.filter(
            inspection__form__compliance_decision='NON_COMPLIANT',
            payment_status='UNPAID',
            legal_action='NONE'
        )
        
        if needs_escalation.exists():
            recommendations.append({
                'type': 'Legal Escalation Required',
                'description': f"{needs_escalation.count()} non-compliant establishments with unpaid penalties require legal action initiation."
            })
        
        # Pending compliance verification
        pending_verification = queryset.filter(
            inspection__form__nov__isnull=False,
            inspection__form__noo__isnull=True,
            inspection__form__compliance_decision='PENDING'
        )
        
        if pending_verification.exists():
            recommendations.append({
                'type': 'Pending Compliance Verification',
                'description': f"{pending_verification.count()} establishments require re-inspection to verify compliance with NOV."
            })
        
        return Response(recommendations)
    
    @action(detail=False, methods=['get'])
    def export_pdf(self, request):
        """Export report as PDF"""
        from django.http import HttpResponse, JsonResponse
        from .legal_report_pdf import LegalReportPDFGenerator
        import io
        import logging
        import traceback
        
        logger = logging.getLogger(__name__)
        
        try:
            # Get filtered data
            queryset = self._get_base_queryset(request)
            queryset = queryset.order_by('-created_at')[:100]  # Limit to 100 records
            
            serializer = LegalReportSerializer(queryset, many=True)
            
            # Get statistics
            try:
                stats_view = self.statistics(request)
                statistics = stats_view.data
            except Exception as e:
                logger.error(f"Error getting statistics: {str(e)}\n{traceback.format_exc()}")
                statistics = {
                    'billing_summary': {
                        'total_billed': 0,
                        'total_paid': 0,
                        'outstanding_balance': 0,
                        'avg_days_to_payment': 0,
                        'total_nov': 0,
                        'total_noo': 0,
                    },
                    'compliance_summary': {
                        'compliant_count': 0,
                        'non_compliant_count': 0,
                        'pending_count': 0,
                        'reinspection_recommended': 0,
                    }
                }
            
            # Get recommendations
            try:
                recs_view = self.recommendations(request)
                recommendations = recs_view.data
            except Exception as e:
                logger.error(f"Error getting recommendations: {str(e)}\n{traceback.format_exc()}")
                recommendations = []
            
            # Prepare report data
            report_data = {
                'records': serializer.data,
                'statistics': statistics,
                'recommendations': recommendations,
            }
            
            # Prepare filters applied
            filters_applied = {}
            filter_params = [
                'billing_date_from', 'billing_date_to', 'payment_date_from', 'payment_date_to',
                'establishment', 'inspection_code', 'payment_status', 'legal_action',
                'law', 'compliance_status'
            ]
            for param in filter_params:
                value = request.query_params.get(param)
                if value:
                    filters_applied[param] = value
            
            # Generate PDF
            try:
                buffer = io.BytesIO()
                generator = LegalReportPDFGenerator(buffer, report_data, filters_applied, request.user)
                generator.generate()
                
                buffer.seek(0)
                
                # Return PDF response
                response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="legal_report_{timezone.now().strftime("%Y%m%d_%H%M%S")}.pdf"'
                
                return response
            except Exception as e:
                logger.error(f"Error generating PDF: {str(e)}\n{traceback.format_exc()}")
                return JsonResponse({
                    'error': 'Failed to generate PDF',
                    'detail': str(e)
                }, status=500)
                
        except Exception as e:
            logger.error(f"Error in export_pdf: {str(e)}\n{traceback.format_exc()}")
            return JsonResponse({
                'error': 'Failed to export PDF',
                'detail': str(e)
            }, status=500)
    
    @action(detail=False, methods=['get'])
    def export_excel(self, request):
        """Export report as Excel"""
        from django.http import HttpResponse
        from .excel_generator import LegalReportExcelGenerator
        
        # Get filtered data
        queryset = self._get_base_queryset(request)
        queryset = queryset.order_by('-created_at')[:500]  # Limit to 500 records
        
        serializer = LegalReportSerializer(queryset, many=True)
        
        # Get statistics
        stats_view = self.statistics(request)
        statistics = stats_view.data
        
        # Get recommendations
        recs_view = self.recommendations(request)
        recommendations = recs_view.data
        
        # Prepare report data
        report_data = {
            'records': serializer.data,
            'statistics': statistics,
            'recommendations': recommendations,
        }
        
        # Prepare filters applied
        filters_applied = {}
        filter_params = [
            'billing_date_from', 'billing_date_to', 'payment_date_from', 'payment_date_to',
            'establishment', 'inspection_code', 'payment_status', 'legal_action',
            'law', 'compliance_status'
        ]
        for param in filter_params:
            value = request.query_params.get(param)
            if value:
                filters_applied[param] = value
        
        # Generate Excel
        generator = LegalReportExcelGenerator(report_data, filters_applied)
        output = generator.generate()
        
        # Return Excel response
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="legal_report_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx"'
        
        return response


class DivisionReportViewSet(viewsets.ViewSet):
    """
    ViewSet for Division Report Generation
    Provides comprehensive reporting with filtering, statistics, and export capabilities
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def _get_base_queryset(self, request):
        """Get base queryset with filters applied"""
        from django.db.models import Q
        
        queryset = Inspection.objects.all()
        
        # Access control - Division Chief and Admin can see all
        user = request.user
        if user.userlevel not in ['Division Chief', 'Admin']:
            # Others can only see inspections they created or are assigned to
            queryset = queryset.filter(
                Q(created_by=user) | Q(assigned_to=user)
            )
        
        # Date filters
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        # Establishment filter
        establishment = request.query_params.get('establishment')
        if establishment:
            # Try to convert to int for ID lookup, if fails only search by name
            try:
                establishment_id = int(establishment)
                queryset = queryset.filter(
                    Q(establishments__name__icontains=establishment) |
                    Q(establishments__id=establishment_id)
                ).distinct()
            except (ValueError, TypeError):
                queryset = queryset.filter(
                    Q(establishments__name__icontains=establishment)
                ).distinct()
        
        # Inspection code filter
        inspection_code = request.query_params.get('inspection_code')
        if inspection_code:
            queryset = queryset.filter(code__icontains=inspection_code)
        
        # Inspection status filter
        inspection_status = request.query_params.get('inspection_status')
        if inspection_status and inspection_status != 'ALL':
            queryset = queryset.filter(current_status=inspection_status)
        
        # Law filter
        law = request.query_params.get('law')
        if law and law != 'ALL':
            queryset = queryset.filter(law__icontains=law.replace('-', ''))
        
        # Compliance status filter (requires join with inspection form)
        compliance_status = request.query_params.get('compliance_status')
        if compliance_status and compliance_status != 'ALL':
            # Handle cases where form might not exist - treat missing forms as PENDING
            if compliance_status == 'PENDING':
                queryset = queryset.filter(
                    Q(form__compliance_decision__isnull=True) |
                    Q(form__compliance_decision='PENDING') |
                    Q(form__isnull=True)
                )
            else:
                queryset = queryset.filter(form__compliance_decision=compliance_status)
        
        # NOV/NOO filter
        has_nov = request.query_params.get('has_nov')
        if has_nov == 'true':
            queryset = queryset.filter(form__nov__isnull=False)
        elif has_nov == 'false':
            queryset = queryset.filter(
                Q(form__nov__isnull=True) | Q(form__isnull=True)
            )
        
        has_noo = request.query_params.get('has_noo')
        if has_noo == 'true':
            queryset = queryset.filter(form__noo__isnull=False)
        elif has_noo == 'false':
            queryset = queryset.filter(
                Q(form__noo__isnull=True) | Q(form__isnull=True)
            )
        
        # Optimize queries - use prefetch for form to handle cases where form might not exist
        queryset = queryset.select_related(
            'created_by',
            'assigned_to'
        ).prefetch_related(
            'establishments',
            'form',
            'form__nov',
            'form__noo',
            'form__inspected_by'
        )
        
        return queryset
    
    def list(self, request):
        """Get filtered inspections for report"""
        from core.pagination import StandardResultsSetPagination
        import logging
        
        logger = logging.getLogger(__name__)
        
        queryset = self._get_base_queryset(request)
        queryset = queryset.order_by('-created_at')
        
        # Log query info for debugging
        total_count = queryset.count()
        logger.info(f"Division Report Query - Total records before pagination: {total_count}")
        logger.info(f"Division Report Query - Filters: {dict(request.query_params)}")
        
        # Pagination
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = DivisionReportSerializer(page, many=True, context={'request': request})
            response_data = paginator.get_paginated_response(serializer.data)
            logger.info(f"Division Report Query - Returning {len(serializer.data)} records (paginated)")
            return response_data
        
        serializer = DivisionReportSerializer(queryset, many=True, context={'request': request})
        logger.info(f"Division Report Query - Returning {len(serializer.data)} records (non-paginated)")
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get computed summary statistics"""
        from django.db.models import Count, Q
        
        queryset = self._get_base_queryset(request)
        
        # Inspection summary
        total_inspections = queryset.count()
        by_status = queryset.values('current_status').annotate(count=Count('id'))
        status_breakdown = {item['current_status']: item['count'] for item in by_status}
        
        # Count NOV/NOO
        total_nov = queryset.filter(form__nov__isnull=False).count()
        total_noo = queryset.filter(form__noo__isnull=False).count()
        
        # Compliance summary
        compliant_count = queryset.filter(
            form__compliance_decision='COMPLIANT'
        ).count()
        non_compliant_count = queryset.filter(
            form__compliance_decision='NON_COMPLIANT'
        ).count()
        pending_count = queryset.filter(
            Q(form__compliance_decision__isnull=True) |
            Q(form__compliance_decision='PENDING') |
            Q(form__isnull=True)
        ).count()
        
        # Division review summary
        division_reviewed = queryset.filter(current_status='DIVISION_REVIEWED').count()
        section_completed = queryset.filter(
            current_status__in=['SECTION_COMPLETED_COMPLIANT', 'SECTION_COMPLETED_NON_COMPLIANT']
        ).count()
        
        return Response({
            'inspection_summary': {
                'total_inspections': total_inspections,
                'status_breakdown': status_breakdown,
                'division_reviewed': division_reviewed,
                'section_completed': section_completed,
                'total_nov': total_nov,
                'total_noo': total_noo,
            },
            'compliance_summary': {
                'compliant_count': compliant_count,
                'non_compliant_count': non_compliant_count,
                'pending_count': pending_count,
            }
        })
    
    @action(detail=False, methods=['get'])
    def recommendations(self, request):
        """Generate system-based recommendations"""
        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import Count
        
        queryset = self._get_base_queryset(request)
        recommendations = []
        
        # Pending division review (section completed but not reviewed)
        pending_review = queryset.filter(
            current_status__in=['SECTION_COMPLETED_COMPLIANT', 'SECTION_COMPLETED_NON_COMPLIANT']
        )
        
        if pending_review.exists():
            recommendations.append({
                'type': 'Pending Division Review',
                'description': f"{pending_review.count()} inspections are waiting for division review."
            })
        
        # Repeated non-compliance (establishments with 2+ non-compliant inspections)
        repeated_non_compliant = queryset.filter(
            form__compliance_decision='NON_COMPLIANT'
        ).values('establishments__name').annotate(
            count=Count('id', distinct=True)
        ).filter(count__gte=2)
        
        if repeated_non_compliant.exists():
            establishments = [est['establishments__name'] for est in repeated_non_compliant[:5]]
            recommendations.append({
                'type': 'Repeated Non-Compliance',
                'description': f"The following establishments have repeated non-compliance issues: {', '.join(establishments)}. Consider escalated action."
            })
        
        # Inspections requiring legal attention
        needs_legal = queryset.filter(
            current_status='NON_COMPLIANT',
            form__compliance_decision='NON_COMPLIANT'
        )
        
        if needs_legal.exists():
            recommendations.append({
                'type': 'Legal Escalation Required',
                'description': f"{needs_legal.count()} non-compliant inspections require legal unit attention."
            })
        
        # Long pending inspections (30+ days without completion)
        today = timezone.now().date()
        pending_threshold = today - timedelta(days=30)
        long_pending = queryset.filter(
            created_at__lt=pending_threshold,
            current_status__in=['CREATED', 'SECTION_ASSIGNED', 'UNIT_ASSIGNED', 'MONITORING_ASSIGNED']
        )
        
        if long_pending.exists():
            recommendations.append({
                'type': 'Long Pending Inspections',
                'description': f"{long_pending.count()} inspections have been pending for more than 30 days. Follow up required."
            })
        
        return Response(recommendations)
    
    @action(detail=False, methods=['get'])
    def export_pdf(self, request):
        """Export report as PDF"""
        from django.http import HttpResponse
        from .division_report_pdf import DivisionReportPDFGenerator
        import io
        
        # Get filtered data
        queryset = self._get_base_queryset(request)
        queryset = queryset.order_by('-created_at')[:100]  # Limit to 100 records
        
        serializer = DivisionReportSerializer(queryset, many=True, context={'request': request})
        
        # Get statistics
        stats_view = self.statistics(request)
        statistics = stats_view.data
        
        # Get recommendations
        recs_view = self.recommendations(request)
        recommendations = recs_view.data
        
        # Prepare report data
        report_data = {
            'records': serializer.data,
            'statistics': statistics,
            'recommendations': recommendations,
        }
        
        # Prepare filters applied
        filters_applied = {}
        filter_params = [
            'date_from', 'date_to', 'establishment', 'inspection_code',
            'inspection_status', 'law', 'compliance_status'
        ]
        for param in filter_params:
            value = request.query_params.get(param)
            if value:
                filters_applied[param] = value
        
        # Generate PDF
        buffer = io.BytesIO()
        generator = DivisionReportPDFGenerator(buffer, report_data, filters_applied, request.user)
        generator.generate()
        
        buffer.seek(0)
        
        # Return PDF response
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="division_report_{timezone.now().strftime("%Y%m%d_%H%M%S")}.pdf"'
        
        return response
    
    @action(detail=False, methods=['get'])
    def export_excel(self, request):
        """Export report as Excel"""
        from django.http import HttpResponse
        from .division_report_excel import DivisionReportExcelGenerator
        
        # Get filtered data
        queryset = self._get_base_queryset(request)
        queryset = queryset.order_by('-created_at')[:500]  # Limit to 500 records
        
        serializer = DivisionReportSerializer(queryset, many=True, context={'request': request})
        
        # Get statistics
        stats_view = self.statistics(request)
        statistics = stats_view.data
        
        # Get recommendations
        recs_view = self.recommendations(request)
        recommendations = recs_view.data
        
        # Prepare report data
        report_data = {
            'records': serializer.data,
            'statistics': statistics,
            'recommendations': recommendations,
        }
        
        # Prepare filters applied
        filters_applied = {}
        filter_params = [
            'date_from', 'date_to', 'establishment', 'inspection_code',
            'inspection_status', 'law', 'compliance_status'
        ]
        for param in filter_params:
            value = request.query_params.get(param)
            if value:
                filters_applied[param] = value
        
        # Generate Excel
        generator = DivisionReportExcelGenerator(report_data, filters_applied)
        output = generator.generate()
        
        # Return Excel response
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="division_report_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx"'
        
        return response


class SectionReportViewSet(viewsets.ViewSet):
    """
    ViewSet for Section Report Generation
    Shows only inspections inspected by the current Section Chief user
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def _get_base_queryset(self, request):
        """Get base queryset with filters applied - only inspections inspected by current user"""
        from django.db.models import Q
        
        user = request.user
        
        # Access control - Section Chief and Admin only
        if user.userlevel not in ['Section Chief', 'Admin']:
            return Inspection.objects.none()
        
        # Base filter: only inspections inspected by current user
        queryset = Inspection.objects.filter(form__inspected_by=user)
        
        # Date filters
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        # Establishment filter
        establishment = request.query_params.get('establishment')
        if establishment:
            # Try to convert to int for ID lookup, if fails only search by name
            try:
                establishment_id = int(establishment)
                queryset = queryset.filter(
                    Q(establishments__name__icontains=establishment) |
                    Q(establishments__id=establishment_id)
                ).distinct()
            except (ValueError, TypeError):
                queryset = queryset.filter(
                    Q(establishments__name__icontains=establishment)
                ).distinct()
        
        # Inspection code filter
        inspection_code = request.query_params.get('inspection_code')
        if inspection_code:
            queryset = queryset.filter(code__icontains=inspection_code)
        
        # Inspection status filter
        inspection_status = request.query_params.get('inspection_status')
        if inspection_status and inspection_status != 'ALL':
            queryset = queryset.filter(current_status=inspection_status)
        
        # Law filter
        law = request.query_params.get('law')
        if law and law != 'ALL':
            queryset = queryset.filter(law__icontains=law.replace('-', ''))
        
        # Compliance status filter
        compliance_status = request.query_params.get('compliance_status')
        if compliance_status and compliance_status != 'ALL':
            if compliance_status == 'PENDING':
                queryset = queryset.filter(
                    Q(form__compliance_decision__isnull=True) |
                    Q(form__compliance_decision='PENDING') |
                    Q(form__isnull=True)
                )
            else:
                queryset = queryset.filter(form__compliance_decision=compliance_status)
        
        # NOV/NOO filter
        has_nov = request.query_params.get('has_nov')
        if has_nov == 'true':
            queryset = queryset.filter(form__nov__isnull=False)
        elif has_nov == 'false':
            queryset = queryset.filter(
                Q(form__nov__isnull=True) | Q(form__isnull=True)
            )
        
        has_noo = request.query_params.get('has_noo')
        if has_noo == 'true':
            queryset = queryset.filter(form__noo__isnull=False)
        elif has_noo == 'false':
            queryset = queryset.filter(
                Q(form__noo__isnull=True) | Q(form__isnull=True)
            )
        
        # Optimize queries
        queryset = queryset.select_related(
            'created_by',
            'assigned_to'
        ).prefetch_related(
            'establishments',
            'form',
            'form__nov',
            'form__noo',
            'form__inspected_by'
        )
        
        return queryset
    
    def list(self, request):
        """Get filtered inspections for report"""
        from core.pagination import StandardResultsSetPagination
        import logging
        
        logger = logging.getLogger(__name__)
        
        queryset = self._get_base_queryset(request)
        queryset = queryset.order_by('-created_at')
        
        total_count = queryset.count()
        logger.info(f"Section Report Query - Total records before pagination: {total_count}")
        logger.info(f"Section Report Query - Filters: {dict(request.query_params)}")
        
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = DivisionReportSerializer(page, many=True, context={'request': request})
            response_data = paginator.get_paginated_response(serializer.data)
            logger.info(f"Section Report Query - Returning {len(serializer.data)} records (paginated)")
            return response_data
        
        serializer = DivisionReportSerializer(queryset, many=True, context={'request': request})
        logger.info(f"Section Report Query - Returning {len(serializer.data)} records (non-paginated)")
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get computed summary statistics"""
        from django.db.models import Count, Q
        
        queryset = self._get_base_queryset(request)
        
        total_inspections = queryset.count()
        by_status = queryset.values('current_status').annotate(count=Count('id'))
        status_breakdown = {item['current_status']: item['count'] for item in by_status}
        
        total_nov = queryset.filter(form__nov__isnull=False).count()
        total_noo = queryset.filter(form__noo__isnull=False).count()
        
        compliant_count = queryset.filter(form__compliance_decision='COMPLIANT').count()
        non_compliant_count = queryset.filter(form__compliance_decision='NON_COMPLIANT').count()
        pending_count = queryset.filter(
            Q(form__compliance_decision__isnull=True) |
            Q(form__compliance_decision='PENDING') |
            Q(form__isnull=True)
        ).count()
        
        return Response({
            'inspection_summary': {
                'total_inspections': total_inspections,
                'status_breakdown': status_breakdown,
                'total_nov': total_nov,
                'total_noo': total_noo,
            },
            'compliance_summary': {
                'compliant_count': compliant_count,
                'non_compliant_count': non_compliant_count,
                'pending_count': pending_count,
            }
        })
    
    @action(detail=False, methods=['get'])
    def recommendations(self, request):
        """Generate system-based recommendations"""
        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import Count
        
        queryset = self._get_base_queryset(request)
        recommendations = []
        
        # Non-compliant inspections requiring follow-up
        non_compliant = queryset.filter(form__compliance_decision='NON_COMPLIANT')
        if non_compliant.exists():
            recommendations.append({
                'type': 'Non-Compliant Inspections',
                'description': f"{non_compliant.count()} inspections are marked as non-compliant. Follow-up actions may be required."
            })
        
        return Response(recommendations)
    
    @action(detail=False, methods=['get'])
    def export_pdf(self, request):
        """Export report as PDF"""
        from django.http import HttpResponse
        from .division_report_pdf import DivisionReportPDFGenerator
        import io
        
        queryset = self._get_base_queryset(request)
        queryset = queryset.order_by('-created_at')[:100]
        
        serializer = DivisionReportSerializer(queryset, many=True, context={'request': request})
        
        stats_view = self.statistics(request)
        statistics = stats_view.data
        
        recs_view = self.recommendations(request)
        recommendations = recs_view.data
        
        report_data = {
            'records': serializer.data,
            'statistics': statistics,
            'recommendations': recommendations,
        }
        
        filters_applied = {}
        filter_params = ['date_from', 'date_to', 'establishment', 'inspection_code', 'inspection_status', 'law', 'compliance_status']
        for param in filter_params:
            value = request.query_params.get(param)
            if value:
                filters_applied[param] = value
        
        buffer = io.BytesIO()
        generator = DivisionReportPDFGenerator(buffer, report_data, filters_applied, request.user)
        # Override title for section report
        def _add_title_page_section():
            from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.units import inch
            from reportlab.lib import colors
            from datetime import datetime
            title_text = "<para align='center'><b><font size='18' color='#0066CC'>SECTION REPORT</font></b></para>"
            generator.story.append(Paragraph(title_text, generator.styles['DENRTitle']))
            subtitle_text = "<para align='center'><font size='14' color='#008000'>Inspection Summary Report</font></para>"
            generator.story.append(Paragraph(subtitle_text, generator.styles['DENRSubtitle']))
            generator.story.append(Spacer(1, 0.2*inch))
            gen_date = datetime.now().strftime("%B %d, %Y")
            date_text = f"<para align='center'><font size='10'>Generated on: {gen_date}</font></para>"
            generator.story.append(Paragraph(date_text, generator.styles['DENRBody']))
            generator.story.append(Spacer(1, 0.3*inch))
            # Add metadata table
            metadata_data = [
                ['Reference Number:', generator.reference_number],
                ['Prepared by:', f"{request.user.first_name} {request.user.last_name}"],
                ['User Level:', request.user.userlevel],
                ['Email:', request.user.email],
                ['Generated:', datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
            ]
            metadata_table = Table(metadata_data, colWidths=[2*inch, 4*inch])
            metadata_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('PADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, generator.border_gray),
                ('BACKGROUND', (0, 0), (0, -1), generator.light_blue),
            ]))
            generator.story.append(metadata_table)
            generator.story.append(Spacer(1, 0.3*inch))
            # Legal bases section
            generator.story.append(Paragraph("<b>LEGAL BASES</b>", generator.styles['SectionHeader']))
            legal_bases = generator._get_legal_bases()
            for base in legal_bases:
                base_text = f"<bullet>&bull;</bullet> {base}"
                generator.story.append(Paragraph(base_text, generator.styles['DENRBody']))
            generator.story.append(Spacer(1, 0.3*inch))
            # Add filters if any
            if filters_applied:
                filter_data = [['FILTERS APPLIED:', '']]
                for key, value in filters_applied.items():
                    if value:
                        filter_data.append([key.replace('_', ' ').title() + ':', str(value)])
                if len(filter_data) > 1:
                    filter_table = Table(filter_data, colWidths=[2*inch, 4*inch])
                    filter_table.setStyle(TableStyle([
                        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (0, 0), 11),
                        ('BACKGROUND', (0, 0), (-1, 0), generator.light_blue),
                        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
                        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 1), (-1, -1), 9),
                        ('PADDING', (0, 0), (-1, -1), 6),
                        ('GRID', (0, 0), (-1, -1), 0.5, generator.border_gray),
                    ]))
                    generator.story.append(filter_table)
                    generator.story.append(Spacer(1, 0.3*inch))
        generator._add_title_page = _add_title_page_section
        generator.generate()
        
        buffer.seek(0)
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="section_report_{timezone.now().strftime("%Y%m%d_%H%M%S")}.pdf"'
        return response
    
    @action(detail=False, methods=['get'])
    def export_excel(self, request):
        """Export report as Excel"""
        from django.http import HttpResponse
        from .section_report_excel import SectionReportExcelGenerator
        
        queryset = self._get_base_queryset(request)
        queryset = queryset.order_by('-created_at')[:500]
        
        serializer = DivisionReportSerializer(queryset, many=True, context={'request': request})
        
        stats_view = self.statistics(request)
        statistics = stats_view.data
        
        recs_view = self.recommendations(request)
        recommendations = recs_view.data
        
        report_data = {
            'records': serializer.data,
            'statistics': statistics,
            'recommendations': recommendations,
        }
        
        filters_applied = {}
        filter_params = ['date_from', 'date_to', 'establishment', 'inspection_code', 'inspection_status', 'law', 'compliance_status']
        for param in filter_params:
            value = request.query_params.get(param)
            if value:
                filters_applied[param] = value
        
        generator = SectionReportExcelGenerator(report_data, filters_applied)
        output = generator.generate()
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="section_report_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx"'
        return response


class UnitReportViewSet(viewsets.ViewSet):
    """
    ViewSet for Unit Report Generation
    Shows only inspections inspected by the current Unit Head user
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def _get_base_queryset(self, request):
        """Get base queryset with filters applied - only inspections inspected by current user"""
        from django.db.models import Q
        
        user = request.user
        
        # Access control - Unit Head and Admin only
        if user.userlevel not in ['Unit Head', 'Admin']:
            return Inspection.objects.none()
        
        # Base filter: only inspections inspected by current user
        queryset = Inspection.objects.filter(form__inspected_by=user)
        
        # Date filters
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        # Establishment filter
        establishment = request.query_params.get('establishment')
        if establishment:
            # Try to convert to int for ID lookup, if fails only search by name
            try:
                establishment_id = int(establishment)
                queryset = queryset.filter(
                    Q(establishments__name__icontains=establishment) |
                    Q(establishments__id=establishment_id)
                ).distinct()
            except (ValueError, TypeError):
                queryset = queryset.filter(
                    Q(establishments__name__icontains=establishment)
                ).distinct()
        
        # Inspection code filter
        inspection_code = request.query_params.get('inspection_code')
        if inspection_code:
            queryset = queryset.filter(code__icontains=inspection_code)
        
        # Inspection status filter
        inspection_status = request.query_params.get('inspection_status')
        if inspection_status and inspection_status != 'ALL':
            queryset = queryset.filter(current_status=inspection_status)
        
        # Law filter
        law = request.query_params.get('law')
        if law and law != 'ALL':
            queryset = queryset.filter(law__icontains=law.replace('-', ''))
        
        # Compliance status filter
        compliance_status = request.query_params.get('compliance_status')
        if compliance_status and compliance_status != 'ALL':
            if compliance_status == 'PENDING':
                queryset = queryset.filter(
                    Q(form__compliance_decision__isnull=True) |
                    Q(form__compliance_decision='PENDING') |
                    Q(form__isnull=True)
                )
            else:
                queryset = queryset.filter(form__compliance_decision=compliance_status)
        
        # NOV/NOO filter
        has_nov = request.query_params.get('has_nov')
        if has_nov == 'true':
            queryset = queryset.filter(form__nov__isnull=False)
        elif has_nov == 'false':
            queryset = queryset.filter(
                Q(form__nov__isnull=True) | Q(form__isnull=True)
            )
        
        has_noo = request.query_params.get('has_noo')
        if has_noo == 'true':
            queryset = queryset.filter(form__noo__isnull=False)
        elif has_noo == 'false':
            queryset = queryset.filter(
                Q(form__noo__isnull=True) | Q(form__isnull=True)
            )
        
        # Optimize queries
        queryset = queryset.select_related(
            'created_by',
            'assigned_to'
        ).prefetch_related(
            'establishments',
            'form',
            'form__nov',
            'form__noo',
            'form__inspected_by'
        )
        
        return queryset
    
    def list(self, request):
        """Get filtered inspections for report"""
        from core.pagination import StandardResultsSetPagination
        import logging
        
        logger = logging.getLogger(__name__)
        
        queryset = self._get_base_queryset(request)
        queryset = queryset.order_by('-created_at')
        
        total_count = queryset.count()
        logger.info(f"Unit Report Query - Total records before pagination: {total_count}")
        logger.info(f"Unit Report Query - Filters: {dict(request.query_params)}")
        
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = DivisionReportSerializer(page, many=True, context={'request': request})
            response_data = paginator.get_paginated_response(serializer.data)
            logger.info(f"Unit Report Query - Returning {len(serializer.data)} records (paginated)")
            return response_data
        
        serializer = DivisionReportSerializer(queryset, many=True, context={'request': request})
        logger.info(f"Unit Report Query - Returning {len(serializer.data)} records (non-paginated)")
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get computed summary statistics"""
        from django.db.models import Count, Q
        
        queryset = self._get_base_queryset(request)
        
        total_inspections = queryset.count()
        by_status = queryset.values('current_status').annotate(count=Count('id'))
        status_breakdown = {item['current_status']: item['count'] for item in by_status}
        
        total_nov = queryset.filter(form__nov__isnull=False).count()
        total_noo = queryset.filter(form__noo__isnull=False).count()
        
        compliant_count = queryset.filter(form__compliance_decision='COMPLIANT').count()
        non_compliant_count = queryset.filter(form__compliance_decision='NON_COMPLIANT').count()
        pending_count = queryset.filter(
            Q(form__compliance_decision__isnull=True) |
            Q(form__compliance_decision='PENDING') |
            Q(form__isnull=True)
        ).count()
        
        return Response({
            'inspection_summary': {
                'total_inspections': total_inspections,
                'status_breakdown': status_breakdown,
                'total_nov': total_nov,
                'total_noo': total_noo,
            },
            'compliance_summary': {
                'compliant_count': compliant_count,
                'non_compliant_count': non_compliant_count,
                'pending_count': pending_count,
            }
        })
    
    @action(detail=False, methods=['get'])
    def recommendations(self, request):
        """Generate system-based recommendations"""
        from django.db.models import Count
        
        queryset = self._get_base_queryset(request)
        recommendations = []
        
        # Non-compliant inspections requiring follow-up
        non_compliant = queryset.filter(form__compliance_decision='NON_COMPLIANT')
        if non_compliant.exists():
            recommendations.append({
                'type': 'Non-Compliant Inspections',
                'description': f"{non_compliant.count()} inspections are marked as non-compliant. Follow-up actions may be required."
            })
        
        return Response(recommendations)
    
    @action(detail=False, methods=['get'])
    def export_pdf(self, request):
        """Export report as PDF"""
        from django.http import HttpResponse
        from .division_report_pdf import DivisionReportPDFGenerator
        import io
        
        queryset = self._get_base_queryset(request)
        queryset = queryset.order_by('-created_at')[:100]
        
        serializer = DivisionReportSerializer(queryset, many=True, context={'request': request})
        
        stats_view = self.statistics(request)
        statistics = stats_view.data
        
        recs_view = self.recommendations(request)
        recommendations = recs_view.data
        
        report_data = {
            'records': serializer.data,
            'statistics': statistics,
            'recommendations': recommendations,
        }
        
        filters_applied = {}
        filter_params = ['date_from', 'date_to', 'establishment', 'inspection_code', 'inspection_status', 'law', 'compliance_status']
        for param in filter_params:
            value = request.query_params.get(param)
            if value:
                filters_applied[param] = value
        
        buffer = io.BytesIO()
        generator = DivisionReportPDFGenerator(buffer, report_data, filters_applied, request.user)
        # Override title for unit report
        def _add_title_page_unit():
            from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.units import inch
            from reportlab.lib import colors
            from datetime import datetime
            title_text = "<para align='center'><b><font size='18' color='#0066CC'>UNIT REPORT</font></b></para>"
            generator.story.append(Paragraph(title_text, generator.styles['DENRTitle']))
            subtitle_text = "<para align='center'><font size='14' color='#008000'>Inspection Summary Report</font></para>"
            generator.story.append(Paragraph(subtitle_text, generator.styles['DENRSubtitle']))
            generator.story.append(Spacer(1, 0.2*inch))
            gen_date = datetime.now().strftime("%B %d, %Y")
            date_text = f"<para align='center'><font size='10'>Generated on: {gen_date}</font></para>"
            generator.story.append(Paragraph(date_text, generator.styles['DENRBody']))
            generator.story.append(Spacer(1, 0.3*inch))
            # Add metadata table
            metadata_data = [
                ['Reference Number:', generator.reference_number],
                ['Prepared by:', f"{request.user.first_name} {request.user.last_name}"],
                ['User Level:', request.user.userlevel],
                ['Email:', request.user.email],
                ['Generated:', datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
            ]
            metadata_table = Table(metadata_data, colWidths=[2*inch, 4*inch])
            metadata_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('PADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, generator.border_gray),
                ('BACKGROUND', (0, 0), (0, -1), generator.light_blue),
            ]))
            generator.story.append(metadata_table)
            generator.story.append(Spacer(1, 0.3*inch))
            # Legal bases section
            generator.story.append(Paragraph("<b>LEGAL BASES</b>", generator.styles['SectionHeader']))
            legal_bases = generator._get_legal_bases()
            for base in legal_bases:
                base_text = f"<bullet>&bull;</bullet> {base}"
                generator.story.append(Paragraph(base_text, generator.styles['DENRBody']))
            generator.story.append(Spacer(1, 0.3*inch))
            # Add filters if any
            if filters_applied:
                filter_data = [['FILTERS APPLIED:', '']]
                for key, value in filters_applied.items():
                    if value:
                        filter_data.append([key.replace('_', ' ').title() + ':', str(value)])
                if len(filter_data) > 1:
                    filter_table = Table(filter_data, colWidths=[2*inch, 4*inch])
                    filter_table.setStyle(TableStyle([
                        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (0, 0), 11),
                        ('BACKGROUND', (0, 0), (-1, 0), generator.light_blue),
                        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
                        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 1), (-1, -1), 9),
                        ('PADDING', (0, 0), (-1, -1), 6),
                        ('GRID', (0, 0), (-1, -1), 0.5, generator.border_gray),
                    ]))
                    generator.story.append(filter_table)
                    generator.story.append(Spacer(1, 0.3*inch))
        generator._add_title_page = _add_title_page_unit
        generator.generate()
        
        buffer.seek(0)
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="unit_report_{timezone.now().strftime("%Y%m%d_%H%M%S")}.pdf"'
        return response
    
    @action(detail=False, methods=['get'])
    def export_excel(self, request):
        """Export report as Excel"""
        from django.http import HttpResponse
        from .unit_report_excel import UnitReportExcelGenerator
        
        queryset = self._get_base_queryset(request)
        queryset = queryset.order_by('-created_at')[:500]
        
        serializer = DivisionReportSerializer(queryset, many=True, context={'request': request})
        
        stats_view = self.statistics(request)
        statistics = stats_view.data
        
        recs_view = self.recommendations(request)
        recommendations = recs_view.data
        
        report_data = {
            'records': serializer.data,
            'statistics': statistics,
            'recommendations': recommendations,
        }
        
        filters_applied = {}
        filter_params = ['date_from', 'date_to', 'establishment', 'inspection_code', 'inspection_status', 'law', 'compliance_status']
        for param in filter_params:
            value = request.query_params.get(param)
            if value:
                filters_applied[param] = value
        
        generator = UnitReportExcelGenerator(report_data, filters_applied)
        output = generator.generate()
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="unit_report_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx"'
        return response


class MonitoringReportViewSet(viewsets.ViewSet):
    """
    ViewSet for Monitoring Report Generation
    Shows only inspections inspected by the current Monitoring Personnel user
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def _get_base_queryset(self, request):
        """Get base queryset with filters applied - only inspections inspected by current user"""
        from django.db.models import Q
        
        user = request.user
        
        # Access control - Monitoring Personnel and Admin only
        if user.userlevel not in ['Monitoring Personnel', 'Admin']:
            return Inspection.objects.none()
        
        # Base filter: only inspections inspected by current user
        queryset = Inspection.objects.filter(form__inspected_by=user)
        
        # Date filters
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        # Establishment filter
        establishment = request.query_params.get('establishment')
        if establishment:
            # Try to convert to int for ID lookup, if fails only search by name
            try:
                establishment_id = int(establishment)
                queryset = queryset.filter(
                    Q(establishments__name__icontains=establishment) |
                    Q(establishments__id=establishment_id)
                ).distinct()
            except (ValueError, TypeError):
                queryset = queryset.filter(
                    Q(establishments__name__icontains=establishment)
                ).distinct()
        
        # Inspection code filter
        inspection_code = request.query_params.get('inspection_code')
        if inspection_code:
            queryset = queryset.filter(code__icontains=inspection_code)
        
        # Inspection status filter
        inspection_status = request.query_params.get('inspection_status')
        if inspection_status and inspection_status != 'ALL':
            queryset = queryset.filter(current_status=inspection_status)
        
        # Law filter
        law = request.query_params.get('law')
        if law and law != 'ALL':
            queryset = queryset.filter(law__icontains=law.replace('-', ''))
        
        # Compliance status filter
        compliance_status = request.query_params.get('compliance_status')
        if compliance_status and compliance_status != 'ALL':
            if compliance_status == 'PENDING':
                queryset = queryset.filter(
                    Q(form__compliance_decision__isnull=True) |
                    Q(form__compliance_decision='PENDING') |
                    Q(form__isnull=True)
                )
            else:
                queryset = queryset.filter(form__compliance_decision=compliance_status)
        
        # NOV/NOO filter
        has_nov = request.query_params.get('has_nov')
        if has_nov == 'true':
            queryset = queryset.filter(form__nov__isnull=False)
        elif has_nov == 'false':
            queryset = queryset.filter(
                Q(form__nov__isnull=True) | Q(form__isnull=True)
            )
        
        has_noo = request.query_params.get('has_noo')
        if has_noo == 'true':
            queryset = queryset.filter(form__noo__isnull=False)
        elif has_noo == 'false':
            queryset = queryset.filter(
                Q(form__noo__isnull=True) | Q(form__isnull=True)
            )
        
        # Optimize queries
        queryset = queryset.select_related(
            'created_by',
            'assigned_to'
        ).prefetch_related(
            'establishments',
            'form',
            'form__nov',
            'form__noo',
            'form__inspected_by'
        )
        
        return queryset
    
    def list(self, request):
        """Get filtered inspections for report"""
        from core.pagination import StandardResultsSetPagination
        import logging
        
        logger = logging.getLogger(__name__)
        
        queryset = self._get_base_queryset(request)
        queryset = queryset.order_by('-created_at')
        
        total_count = queryset.count()
        logger.info(f"Monitoring Report Query - Total records before pagination: {total_count}")
        logger.info(f"Monitoring Report Query - Filters: {dict(request.query_params)}")
        
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = DivisionReportSerializer(page, many=True, context={'request': request})
            response_data = paginator.get_paginated_response(serializer.data)
            logger.info(f"Monitoring Report Query - Returning {len(serializer.data)} records (paginated)")
            return response_data
        
        serializer = DivisionReportSerializer(queryset, many=True, context={'request': request})
        logger.info(f"Monitoring Report Query - Returning {len(serializer.data)} records (non-paginated)")
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get computed summary statistics"""
        from django.db.models import Count, Q
        
        queryset = self._get_base_queryset(request)
        
        total_inspections = queryset.count()
        by_status = queryset.values('current_status').annotate(count=Count('id'))
        status_breakdown = {item['current_status']: item['count'] for item in by_status}
        
        total_nov = queryset.filter(form__nov__isnull=False).count()
        total_noo = queryset.filter(form__noo__isnull=False).count()
        
        compliant_count = queryset.filter(form__compliance_decision='COMPLIANT').count()
        non_compliant_count = queryset.filter(form__compliance_decision='NON_COMPLIANT').count()
        pending_count = queryset.filter(
            Q(form__compliance_decision__isnull=True) |
            Q(form__compliance_decision='PENDING') |
            Q(form__isnull=True)
        ).count()
        
        return Response({
            'inspection_summary': {
                'total_inspections': total_inspections,
                'status_breakdown': status_breakdown,
                'total_nov': total_nov,
                'total_noo': total_noo,
            },
            'compliance_summary': {
                'compliant_count': compliant_count,
                'non_compliant_count': non_compliant_count,
                'pending_count': pending_count,
            }
        })
    
    @action(detail=False, methods=['get'])
    def recommendations(self, request):
        """Generate system-based recommendations"""
        from django.db.models import Count
        
        queryset = self._get_base_queryset(request)
        recommendations = []
        
        # Non-compliant inspections requiring follow-up
        non_compliant = queryset.filter(form__compliance_decision='NON_COMPLIANT')
        if non_compliant.exists():
            recommendations.append({
                'type': 'Non-Compliant Inspections',
                'description': f"{non_compliant.count()} inspections are marked as non-compliant. Follow-up actions may be required."
            })
        
        return Response(recommendations)
    
    @action(detail=False, methods=['get'])
    def export_pdf(self, request):
        """Export report as PDF"""
        from django.http import HttpResponse
        from .division_report_pdf import DivisionReportPDFGenerator
        import io
        
        queryset = self._get_base_queryset(request)
        queryset = queryset.order_by('-created_at')[:100]
        
        serializer = DivisionReportSerializer(queryset, many=True, context={'request': request})
        
        stats_view = self.statistics(request)
        statistics = stats_view.data
        
        recs_view = self.recommendations(request)
        recommendations = recs_view.data
        
        report_data = {
            'records': serializer.data,
            'statistics': statistics,
            'recommendations': recommendations,
        }
        
        filters_applied = {}
        filter_params = ['date_from', 'date_to', 'establishment', 'inspection_code', 'inspection_status', 'law', 'compliance_status']
        for param in filter_params:
            value = request.query_params.get(param)
            if value:
                filters_applied[param] = value
        
        buffer = io.BytesIO()
        generator = DivisionReportPDFGenerator(buffer, report_data, filters_applied, request.user)
        # Override title for monitoring report
        def _add_title_page_monitoring():
            from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.units import inch
            from reportlab.lib import colors
            from datetime import datetime
            title_text = "<para align='center'><b><font size='18' color='#0066CC'>MONITORING REPORT</font></b></para>"
            generator.story.append(Paragraph(title_text, generator.styles['DENRTitle']))
            subtitle_text = "<para align='center'><font size='14' color='#008000'>Inspection Summary Report</font></para>"
            generator.story.append(Paragraph(subtitle_text, generator.styles['DENRSubtitle']))
            generator.story.append(Spacer(1, 0.2*inch))
            gen_date = datetime.now().strftime("%B %d, %Y")
            date_text = f"<para align='center'><font size='10'>Generated on: {gen_date}</font></para>"
            generator.story.append(Paragraph(date_text, generator.styles['DENRBody']))
            generator.story.append(Spacer(1, 0.3*inch))
            # Add metadata table
            metadata_data = [
                ['Reference Number:', generator.reference_number],
                ['Prepared by:', f"{request.user.first_name} {request.user.last_name}"],
                ['User Level:', request.user.userlevel],
                ['Email:', request.user.email],
                ['Generated:', datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
            ]
            metadata_table = Table(metadata_data, colWidths=[2*inch, 4*inch])
            metadata_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('PADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, generator.border_gray),
                ('BACKGROUND', (0, 0), (0, -1), generator.light_blue),
            ]))
            generator.story.append(metadata_table)
            generator.story.append(Spacer(1, 0.3*inch))
            # Legal bases section
            generator.story.append(Paragraph("<b>LEGAL BASES</b>", generator.styles['SectionHeader']))
            legal_bases = generator._get_legal_bases()
            for base in legal_bases:
                base_text = f"<bullet>&bull;</bullet> {base}"
                generator.story.append(Paragraph(base_text, generator.styles['DENRBody']))
            generator.story.append(Spacer(1, 0.3*inch))
            # Add filters if any
            if filters_applied:
                filter_data = [['FILTERS APPLIED:', '']]
                for key, value in filters_applied.items():
                    if value:
                        filter_data.append([key.replace('_', ' ').title() + ':', str(value)])
                if len(filter_data) > 1:
                    filter_table = Table(filter_data, colWidths=[2*inch, 4*inch])
                    filter_table.setStyle(TableStyle([
                        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (0, 0), 11),
                        ('BACKGROUND', (0, 0), (-1, 0), generator.light_blue),
                        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
                        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 1), (-1, -1), 9),
                        ('PADDING', (0, 0), (-1, -1), 6),
                        ('GRID', (0, 0), (-1, -1), 0.5, generator.border_gray),
                    ]))
                    generator.story.append(filter_table)
                    generator.story.append(Spacer(1, 0.3*inch))
        generator._add_title_page = _add_title_page_monitoring
        generator.generate()
        
        buffer.seek(0)
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="monitoring_report_{timezone.now().strftime("%Y%m%d_%H%M%S")}.pdf"'
        return response
    
    @action(detail=False, methods=['get'])
    def export_excel(self, request):
        """Export report as Excel"""
        from django.http import HttpResponse
        from .monitoring_report_excel import MonitoringReportExcelGenerator
        
        queryset = self._get_base_queryset(request)
        queryset = queryset.order_by('-created_at')[:500]
        
        serializer = DivisionReportSerializer(queryset, many=True, context={'request': request})
        
        stats_view = self.statistics(request)
        statistics = stats_view.data
        
        recs_view = self.recommendations(request)
        recommendations = recs_view.data
        
        report_data = {
            'records': serializer.data,
            'statistics': statistics,
            'recommendations': recommendations,
        }
        
        filters_applied = {}
        filter_params = ['date_from', 'date_to', 'establishment', 'inspection_code', 'inspection_status', 'law', 'compliance_status']
        for param in filter_params:
            value = request.query_params.get(param)
            if value:
                filters_applied[param] = value
        
        generator = MonitoringReportExcelGenerator(report_data, filters_applied)
        output = generator.generate()
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="monitoring_report_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx"'
        return response


class AdminReportViewSet(viewsets.ViewSet):
    """
    ViewSet for Admin Report Generation - Establishments and Users
    Provides comprehensive reporting with filtering, statistics, and export capabilities
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def _check_admin_access(self, request):
        """Check if user has admin access"""
        if request.user.userlevel != 'Admin':
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only Admin users can access this report.")
    
    def _get_establishments_queryset(self, request):
        """Get filtered establishments queryset"""
        from establishments.models import Establishment
        from establishments.serializers import AdminReportEstablishmentSerializer
        
        queryset = Establishment.objects.all()
        
        # Date filters
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        # Province filter
        province = request.query_params.get('province')
        if province and province != 'ALL':
            queryset = queryset.filter(province__icontains=province)
        
        # City filter
        city = request.query_params.get('city')
        if city and city != 'ALL':
            queryset = queryset.filter(city__icontains=city)
        
        # Order by created_at descending
        queryset = queryset.order_by('-created_at')
        
        return queryset
    
    def _get_users_queryset(self, request):
        """Get filtered users queryset"""
        from users.serializers import AdminReportUserSerializer
        
        User = get_user_model()
        queryset = User.objects.all()
        
        # Status filter (created or updated)
        status_filter = request.query_params.get('status_filter', 'created')
        
        # Date filters based on status_filter
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        
        if status_filter == 'created':
            if date_from:
                queryset = queryset.filter(date_joined__gte=date_from)
            if date_to:
                queryset = queryset.filter(date_joined__lte=date_to)
        elif status_filter == 'updated':
            if date_from:
                queryset = queryset.filter(updated_at__gte=date_from)
            if date_to:
                queryset = queryset.filter(updated_at__lte=date_to)
        
        # Active status filter
        is_active_filter = request.query_params.get('is_active')
        if is_active_filter == 'true':
            queryset = queryset.filter(is_active=True)
        elif is_active_filter == 'false':
            queryset = queryset.filter(is_active=False)
        
        # Order by date_joined descending
        queryset = queryset.order_by('-date_joined')
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def establishments(self, request):
        """List establishments with pagination"""
        self._check_admin_access(request)
        from core.pagination import StandardResultsSetPagination
        from establishments.serializers import AdminReportEstablishmentSerializer
        
        queryset = self._get_establishments_queryset(request)
        
        # Pagination
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = AdminReportEstablishmentSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        serializer = AdminReportEstablishmentSerializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def users(self, request):
        """List users with pagination"""
        self._check_admin_access(request)
        from core.pagination import StandardResultsSetPagination
        from users.serializers import AdminReportUserSerializer
        
        queryset = self._get_users_queryset(request)
        
        # Pagination
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = AdminReportUserSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        serializer = AdminReportUserSerializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def establishments_statistics(self, request):
        """Get establishments statistics"""
        self._check_admin_access(request)
        from django.db.models import Count
        
        queryset = self._get_establishments_queryset(request)
        
        total = queryset.count()
        active = queryset.filter(is_active=True).count()
        inactive = queryset.filter(is_active=False).count()
        
        # Group by nature of business
        by_nature = queryset.values('nature_of_business').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Group by province
        by_province = queryset.values('province').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        return Response({
            'total': total,
            'active': active,
            'inactive': inactive,
            'by_nature_of_business': list(by_nature),
            'by_province': list(by_province)
        })
    
    @action(detail=False, methods=['get'])
    def users_statistics(self, request):
        """Get users statistics"""
        self._check_admin_access(request)
        from django.db.models import Count
        
        queryset = self._get_users_queryset(request)
        
        total = queryset.count()
        active = queryset.filter(is_active=True).count()
        inactive = queryset.filter(is_active=False).count()
        
        # Group by userlevel
        by_userlevel = queryset.values('userlevel').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Group by section
        by_section = queryset.values('section').annotate(
            count=Count('id')
        ).order_by('-count')
        
        return Response({
            'total': total,
            'active': active,
            'inactive': inactive,
            'by_userlevel': list(by_userlevel),
            'by_section': list(by_section)
        })
    
    @action(detail=False, methods=['get'])
    def filter_options(self, request):
        """Get filter options for establishments"""
        self._check_admin_access(request)
        from establishments.models import Establishment
        
        # Get unique values for filters
        provinces = Establishment.objects.values_list(
            'province', flat=True
        ).distinct().order_by('province')
        
        # Cities (filtered by province if provided)
        province = request.query_params.get('province')
        city_queryset = Establishment.objects.all()
        if province and province != 'ALL':
            city_queryset = city_queryset.filter(province__icontains=province)
        
        cities = city_queryset.values_list(
            'city', flat=True
        ).distinct().order_by('city')
        
        return Response({
            'provinces': list(provinces),
            'cities': list(cities)
        })
    
    @action(detail=False, methods=['get'])
    def export_establishments_pdf(self, request):
        """Export establishments report as PDF"""
        self._check_admin_access(request)
        from django.http import HttpResponse
        from .admin_report_pdf import AdminReportPDFGenerator
        import io
        
        queryset = self._get_establishments_queryset(request)
        from establishments.serializers import AdminReportEstablishmentSerializer
        serializer = AdminReportEstablishmentSerializer(queryset, many=True)
        report_data = serializer.data
        
        # Build filters applied dict
        filters_applied = {
            'Date From': request.query_params.get('date_from', ''),
            'Date To': request.query_params.get('date_to', ''),
            'Province': request.query_params.get('province', 'ALL'),
            'City': request.query_params.get('city', 'ALL'),
        }
        
        buffer = io.BytesIO()
        generator = AdminReportPDFGenerator(buffer, report_data, filters_applied, {
            'name': f"{request.user.first_name} {request.user.last_name}".strip() or request.user.email,
            'userlevel': request.user.userlevel
        })
        generator.generate_establishments_report()
        
        buffer.seek(0)
        response = HttpResponse(
            buffer.read(),
            content_type='application/pdf'
        )
        response['Content-Disposition'] = f'attachment; filename="admin_establishments_report_{timezone.now().strftime("%Y%m%d_%H%M%S")}.pdf"'
        return response
    
    @action(detail=False, methods=['get'])
    def export_users_pdf(self, request):
        """Export users report as PDF"""
        self._check_admin_access(request)
        from django.http import HttpResponse
        from .admin_report_pdf import AdminReportPDFGenerator
        import io
        
        queryset = self._get_users_queryset(request)
        from users.serializers import AdminReportUserSerializer
        serializer = AdminReportUserSerializer(queryset, many=True)
        report_data = serializer.data
        
        # Build filters applied dict
        status_filter = request.query_params.get('status_filter', 'created')
        filters_applied = {
            'Date From': request.query_params.get('date_from', ''),
            'Date To': request.query_params.get('date_to', ''),
            'Status Filter': status_filter.title(),
            'Active Status': request.query_params.get('is_active', 'ALL'),
        }
        
        buffer = io.BytesIO()
        generator = AdminReportPDFGenerator(buffer, report_data, filters_applied, {
            'name': f"{request.user.first_name} {request.user.last_name}".strip() or request.user.email,
            'userlevel': request.user.userlevel
        })
        generator.generate_users_report()
        
        buffer.seek(0)
        response = HttpResponse(
            buffer.read(),
            content_type='application/pdf'
        )
        response['Content-Disposition'] = f'attachment; filename="admin_users_report_{timezone.now().strftime("%Y%m%d_%H%M%S")}.pdf"'
        return response
    
    @action(detail=False, methods=['get'])
    def export_establishments_excel(self, request):
        """Export establishments report as Excel"""
        self._check_admin_access(request)
        from django.http import HttpResponse
        from .admin_report_excel import AdminReportExcelGenerator
        import io
        
        queryset = self._get_establishments_queryset(request)
        from establishments.serializers import AdminReportEstablishmentSerializer
        serializer = AdminReportEstablishmentSerializer(queryset, many=True)
        report_data = serializer.data
        
        # Build filters applied dict
        filters_applied = {
            'Date From': request.query_params.get('date_from', ''),
            'Date To': request.query_params.get('date_to', ''),
            'Province': request.query_params.get('province', 'ALL'),
            'City': request.query_params.get('city', 'ALL'),
        }
        
        output = io.BytesIO()
        generator = AdminReportExcelGenerator(report_data, filters_applied)
        generator.generate_establishments_report()
        generator.workbook.save(output)
        
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="admin_establishments_report_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx"'
        return response
    
    @action(detail=False, methods=['get'])
    def export_users_excel(self, request):
        """Export users report as Excel"""
        self._check_admin_access(request)
        from django.http import HttpResponse
        from .admin_report_excel import AdminReportExcelGenerator
        import io
        
        queryset = self._get_users_queryset(request)
        from users.serializers import AdminReportUserSerializer
        serializer = AdminReportUserSerializer(queryset, many=True)
        report_data = serializer.data
        
        # Build filters applied dict
        status_filter = request.query_params.get('status_filter', 'created')
        filters_applied = {
            'Date From': request.query_params.get('date_from', ''),
            'Date To': request.query_params.get('date_to', ''),
            'Status Filter': status_filter.title(),
            'Active Status': request.query_params.get('is_active', 'ALL'),
        }
        
        output = io.BytesIO()
        generator = AdminReportExcelGenerator(report_data, filters_applied)
        generator.generate_users_report()
        generator.workbook.save(output)
        
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="admin_users_report_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx"'
        return response