from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.db.models import Q
from audit.utils import log_activity
from audit.constants import AUDIT_ACTIONS, AUDIT_MODULES
from .models import Law
from .serializers import LawSerializer


class LawViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Laws.
    Provides CRUD operations and status toggle functionality.
    """
    queryset = Law.objects.all()
    serializer_class = LawSerializer
    permission_classes = [IsAuthenticated]
    
    def get_permissions(self):
        """
        Admin-only for create, update, delete operations.
        All authenticated users can view.
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'toggle_status']:
            return [IsAuthenticated(), IsAdminUser()]
        return [IsAuthenticated()]
    
    def get_queryset(self):
        """
        Filter laws based on query parameters.
        """
        queryset = Law.objects.all()
        
        # Search filter
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(law_title__icontains=search) |
                Q(reference_code__icontains=search) |
                Q(description__icontains=search) |
                Q(category__icontains=search)
            )
        
        # Status filter
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Category filter
        category = self.request.query_params.get('category', None)
        if category:
            queryset = queryset.filter(category__icontains=category)
        
        return queryset
    
    def list(self, request, *args, **kwargs):
        """List all laws"""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def create(self, request, *args, **kwargs):
        """Create a new law"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        law = serializer.save()
        
        # Log activity
        log_activity(
            user=request.user,
            action=AUDIT_ACTIONS["CREATE"],
            module=AUDIT_MODULES["SYSTEM_CONFIG"],
            description=f"Created law: {law.law_title}",
            message=f"Created law '{law.law_title}' ({law.reference_code or 'No code'})",
            metadata={
                "law_id": law.id,
                "law_title": law.law_title,
                "reference_code": law.reference_code,
                "category": law.category,
                "status": "success"
            },
            request=request
        )
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    def update(self, request, *args, **kwargs):
        """Update a law"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        old_data = {
            "law_title": instance.law_title,
            "reference_code": instance.reference_code,
            "category": instance.category,
            "status": instance.status,
        }
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        law = serializer.save()
        
        # Log activity
        log_activity(
            user=request.user,
            action=AUDIT_ACTIONS["UPDATE"],
            module=AUDIT_MODULES["SYSTEM_CONFIG"],
            description=f"Updated law: {law.law_title}",
            message=f"Updated law '{law.law_title}' ({law.reference_code or 'No code'})",
            metadata={
                "law_id": law.id,
                "law_title": law.law_title,
                "reference_code": law.reference_code,
                "category": law.category,
                "status": "success"
            },
            before=old_data,
            after={
                "law_title": law.law_title,
                "reference_code": law.reference_code,
                "category": law.category,
                "status": law.status,
            },
            request=request
        )
        
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def destroy(self, request, *args, **kwargs):
        """Delete a law"""
        instance = self.get_object()
        law_data = {
            "law_title": instance.law_title,
            "reference_code": instance.reference_code,
            "category": instance.category,
        }
        
        instance.delete()
        
        # Log activity
        log_activity(
            user=request.user,
            action=AUDIT_ACTIONS["DELETE"],
            module=AUDIT_MODULES["SYSTEM_CONFIG"],
            description=f"Deleted law: {law_data['law_title']}",
            message=f"Deleted law '{law_data['law_title']}' ({law_data['reference_code'] or 'No code'})",
            metadata={
                "law_title": law_data["law_title"],
                "reference_code": law_data["reference_code"],
                "category": law_data["category"],
                "status": "success"
            },
            before=law_data,
            request=request
        )
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['patch'], url_path='toggle-status')
    def toggle_status(self, request, pk=None):
        """Toggle law status between Active and Inactive"""
        law = self.get_object()
        old_status = law.status
        new_status = 'Inactive' if old_status == 'Active' else 'Active'
        
        law.status = new_status
        law.save()
        
        # Log activity
        log_activity(
            user=request.user,
            action=AUDIT_ACTIONS["UPDATE"],
            module=AUDIT_MODULES["SYSTEM_CONFIG"],
            description=f"Toggled law status: {law.law_title}",
            message=f"Changed status of law '{law.law_title}' from {old_status} to {new_status}",
            metadata={
                "law_id": law.id,
                "law_title": law.law_title,
                "old_status": old_status,
                "new_status": new_status,
                "status": "success"
            },
            before={"status": old_status},
            after={"status": new_status},
            request=request
        )
        
        serializer = self.get_serializer(law)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'], url_path='check-reference-code')
    def check_reference_code(self, request):
        """Check if a reference code already exists"""
        reference_code = request.query_params.get('reference_code', '')
        
        if not reference_code:
            return Response({'exists': False}, status=status.HTTP_200_OK)
        
        # Check if reference code exists (case-insensitive)
        exists = Law.objects.filter(reference_code__iexact=reference_code).exists()
        
        return Response({'exists': exists}, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'], url_path='check-law-title')
    def check_law_title(self, request):
        """Check if a law title already exists (exact match or contains/contained in)"""
        law_title = request.query_params.get('law_title', '')
        exclude_id = request.query_params.get('exclude_id', None)
        
        if not law_title:
            return Response({'exists': False}, status=status.HTTP_200_OK)
        
        # Build queryset
        queryset = Law.objects.all()
        
        # Exclude current law when editing
        if exclude_id:
            queryset = queryset.exclude(id=exclude_id)
        
        # Check for exact match (case-insensitive)
        if queryset.filter(law_title__iexact=law_title).exists():
            return Response({'exists': True}, status=status.HTTP_200_OK)
        
        # Check if new title is contained in any existing title
        # e.g., existing: "Republic Act No. 9003 - Ecological Solid Waste Management"
        #       new: "Ecological Solid Waste Management"
        if queryset.filter(law_title__icontains=law_title).exists():
            return Response({'exists': True}, status=status.HTTP_200_OK)
        
        # Check if any existing title is contained in the new title
        # e.g., existing: "Ecological Solid Waste Management"
        #       new: "Republic Act No. 9003 - Ecological Solid Waste Management"
        existing_titles = queryset.values_list('law_title', flat=True)
        law_title_lower = law_title.lower()
        
        for existing_title in existing_titles:
            if existing_title.lower() in law_title_lower:
                return Response({'exists': True}, status=status.HTTP_200_OK)
        
        return Response({'exists': False}, status=status.HTTP_200_OK)


