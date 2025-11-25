"""
Views for normalized inspection form models
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models_normalized import (
    InspectionFormTemplate, FormSection, FormField, FormFieldResponse,
    InspectionFormInstance, FormSubmission, FormAuditLog, FormManager
)
from .serializers_normalized import (
    InspectionFormTemplateSerializer, FormSectionSerializer, FormFieldSerializer,
    FormFieldResponseSerializer, InspectionFormInstanceSerializer,
    FormSubmissionSerializer, FormAuditLogSerializer, FormDataSerializer,
    FormValidationSerializer, FormTemplateListSerializer
)

User = get_user_model()


class InspectionFormTemplateViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing inspection form templates
    """
    queryset = InspectionFormTemplate.objects.filter(is_active=True)
    serializer_class = InspectionFormTemplateSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return FormTemplateListSerializer
        return InspectionFormTemplateSerializer
    
    @action(detail=True, methods=['post'])
    def create_form_instance(self, request, pk=None):
        """Create a new form instance for an inspection"""
        template = self.get_object()
        inspection_id = request.data.get('inspection_id')
        
        if not inspection_id:
            return Response(
                {'error': 'inspection_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from .models import Inspection
            inspection = Inspection.objects.get(id=inspection_id)
        except Inspection.DoesNotExist:
            return Response(
                {'error': 'Inspection not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if form instance already exists
        if hasattr(inspection, 'form_instance'):
            return Response(
                {'error': 'Form instance already exists for this inspection'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create form instance
        form_instance = FormManager.create_form_instance(inspection, template)
        serializer = InspectionFormInstanceSerializer(form_instance)
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class InspectionFormInstanceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing inspection form instances
    """
    queryset = InspectionFormInstance.objects.all()
    serializer_class = InspectionFormInstanceSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter form instances based on user permissions"""
        user = self.request.user
        
        # Division Chief can see all forms
        if user.userlevel == 'Division Chief':
            return self.queryset.all()
        
        # Other users can only see forms they're assigned to
        return self.queryset.filter(
            inspection__assigned_to=user
        )
    
    @action(detail=True, methods=['post'])
    def save_field_data(self, request, pk=None):
        """Save field data for a form instance"""
        form_instance = self.get_object()
        user = request.user
        
        # Check permissions
        if form_instance.inspection.assigned_to != user:
            return Response(
                {'error': 'You are not assigned to this inspection'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = FormDataSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        field_responses = serializer.validated_data['field_responses']
        saved_responses = []
        errors = {}
        
        for field_id, value in field_responses.items():
            try:
                response = FormManager.save_field_response(
                    form_instance, field_id, value, user
                )
                saved_responses.append(response)
            except Exception as e:
                errors[field_id] = str(e)
        
        if errors:
            return Response(
                {'errors': errors, 'message': 'Some fields could not be saved'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update form status
        if form_instance.status == 'DRAFT':
            form_instance.status = 'IN_PROGRESS'
            form_instance.save()
        
        return Response({
            'message': 'Field data saved successfully',
            'saved_count': len(saved_responses)
        })
    
    @action(detail=True, methods=['post'])
    def validate_form(self, request, pk=None):
        """Validate the form instance"""
        form_instance = self.get_object()
        
        errors = FormManager.validate_form(form_instance)
        is_valid = len(errors) == 0
        
        serializer = FormValidationSerializer({
            'is_valid': is_valid,
            'errors': errors
        })
        
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def submit_form(self, request, pk=None):
        """Submit the form for review"""
        form_instance = self.get_object()
        user = request.user
        
        # Check permissions
        if form_instance.inspection.assigned_to != user:
            return Response(
                {'error': 'You are not assigned to this inspection'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Validate form before submission
        errors = FormManager.validate_form(form_instance)
        if errors:
            return Response(
                {'error': 'Form validation failed', 'errors': errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update form status
        form_instance.status = 'SUBMITTED'
        form_instance.submitted_at = timezone.now()
        form_instance.save()
        
        # Create submission record
        submission, created = FormSubmission.objects.get_or_create(
            form_instance=form_instance,
            defaults={
                'submitted_by': user,
                'approval_status': 'PENDING'
            }
        )
        
        # Create audit log
        FormAuditLog.objects.create(
            form_instance=form_instance,
            action='SUBMIT',
            changed_by=user,
            notes='Form submitted for review'
        )
        
        serializer = FormSubmissionSerializer(submission)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def approve_form(self, request, pk=None):
        """Approve the submitted form"""
        form_instance = self.get_object()
        user = request.user
        
        # Only Division Chief can approve forms
        if user.userlevel != 'Division Chief':
            return Response(
                {'error': 'Only Division Chiefs can approve forms'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            submission = form_instance.submission
        except FormSubmission.DoesNotExist:
            return Response(
                {'error': 'Form has not been submitted'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        approval_notes = request.data.get('approval_notes', '')
        
        # Update submission
        submission.approval_status = 'APPROVED'
        submission.approved_by = user
        submission.approved_at = timezone.now()
        submission.approval_notes = approval_notes
        submission.save()
        
        # Update form instance
        form_instance.status = 'COMPLETED'
        form_instance.completed_at = timezone.now()
        form_instance.save()
        
        # Create audit log
        FormAuditLog.objects.create(
            form_instance=form_instance,
            action='APPROVE',
            changed_by=user,
            notes=f'Form approved: {approval_notes}'
        )
        
        serializer = FormSubmissionSerializer(submission)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def reject_form(self, request, pk=None):
        """Reject the submitted form"""
        form_instance = self.get_object()
        user = request.user
        
        # Only Division Chief can reject forms
        if user.userlevel != 'Division Chief':
            return Response(
                {'error': 'Only Division Chiefs can reject forms'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            submission = form_instance.submission
        except FormSubmission.DoesNotExist:
            return Response(
                {'error': 'Form has not been submitted'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        rejection_notes = request.data.get('rejection_notes', '')
        if not rejection_notes:
            return Response(
                {'error': 'Rejection notes are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update submission
        submission.approval_status = 'REJECTED'
        submission.approved_by = user
        submission.approved_at = timezone.now()
        submission.approval_notes = rejection_notes
        submission.revision_count += 1
        submission.last_revision_at = timezone.now()
        submission.save()
        
        # Update form instance
        form_instance.status = 'IN_PROGRESS'
        form_instance.save()
        
        # Create audit log
        FormAuditLog.objects.create(
            form_instance=form_instance,
            action='REJECT',
            changed_by=user,
            notes=f'Form rejected: {rejection_notes}'
        )
        
        serializer = FormSubmissionSerializer(submission)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def audit_log(self, request, pk=None):
        """Get audit log for the form instance"""
        form_instance = self.get_object()
        audit_logs = form_instance.audit_logs.all()
        serializer = FormAuditLogSerializer(audit_logs, many=True)
        return Response(serializer.data)


class FormFieldResponseViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing individual field responses
    """
    queryset = FormFieldResponse.objects.all()
    serializer_class = FormFieldResponseSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter responses based on user permissions"""
        user = self.request.user
        
        # Division Chief can see all responses
        if user.userlevel == 'Division Chief':
            return self.queryset.all()
        
        # Other users can only see responses for their assigned inspections
        return self.queryset.filter(
            form_instance__inspection__assigned_to=user
        )


class FormSubmissionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing form submissions (read-only)
    """
    queryset = FormSubmission.objects.all()
    serializer_class = FormSubmissionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter submissions based on user permissions"""
        user = self.request.user
        
        # Division Chief can see all submissions
        if user.userlevel == 'Division Chief':
            return self.queryset.all()
        
        # Other users can only see their own submissions
        return self.queryset.filter(
            form_instance__inspection__assigned_to=user
        )
