from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions, generics, viewsets
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.db.models import Q, Prefetch, Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.core.cache import cache

from .models_enhanced_section_grouping import (
    User, UserLevel, Section, SectionGroup, District, UserProfile, 
    UserAssignmentHistory, UserPermission
)
from .serializers_enhanced_section_grouping import (
    UserSerializer, UserListSerializer, RegisterSerializer, UserUpdateSerializer,
    UserLevelSerializer, SectionSerializer, SectionGroupSerializer, DistrictSerializer, 
    UserProfileSerializer, UserAssignmentHistorySerializer, UserPermissionSerializer, 
    MyTokenObtainPairSerializer
)
from .utils.otp_utils import generate_otp, verify_otp, send_otp_email
from notifications.models import Notification
from audit.utils import log_activity


# ---------------------------
# Section Group Management
# ---------------------------
class SectionGroupViewSet(viewsets.ModelViewSet):
    """ViewSet for SectionGroup model with user grouping support"""
    queryset = SectionGroup.objects.filter(is_active=True)
    serializer_class = SectionGroupSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter section groups based on query parameters"""
        queryset = SectionGroup.objects.filter(is_active=True).prefetch_related(
            'sections__users'
        )
        
        # Filter by user count
        min_users = self.request.query_params.get('min_users')
        if min_users:
            queryset = queryset.annotate(
                user_count=Count('sections__users', filter=Q(sections__users__is_active=True))
            ).filter(user_count__gte=int(min_users))
        
        return queryset.order_by('name')
    
    @action(detail=True, methods=['get'])
    def users(self, request, pk=None):
        """Get all users in this section group"""
        section_group = self.get_object()
        users = section_group.get_all_users()
        
        # Apply filters
        userlevel = request.query_params.get('userlevel')
        if userlevel:
            users = users.filter(userlevel__code=userlevel)
        
        district = request.query_params.get('district')
        if district:
            users = users.filter(district__code=district)
        
        serializer = UserListSerializer(users, many=True)
        return Response({
            'section_group': SectionGroupSerializer(section_group).data,
            'users': serializer.data,
            'count': users.count()
        })
    
    @action(detail=True, methods=['get'])
    def users_by_level(self, request, pk=None):
        """Get users in this section group grouped by user level"""
        section_group = self.get_object()
        
        # Get users grouped by level
        users_by_level = {}
        for user_level in UserLevel.objects.filter(is_active=True):
            users = section_group.get_all_users().filter(userlevel=user_level)
            users_by_level[user_level.code] = {
                'user_level': UserLevelSerializer(user_level).data,
                'users': UserListSerializer(users, many=True).data,
                'count': users.count()
            }
        
        return Response({
            'section_group': SectionGroupSerializer(section_group).data,
            'users_by_level': users_by_level
        })
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """Get statistics for this section group"""
        section_group = self.get_object()
        users = section_group.get_all_users()
        
        stats = {
            'total_users': users.count(),
            'active_users': users.filter(is_active=True).count(),
            'inactive_users': users.filter(is_active=False).count(),
            'by_user_level': {},
            'by_district': {},
            'by_section': {}
        }
        
        # Statistics by user level
        for user_level in UserLevel.objects.filter(is_active=True):
            level_users = users.filter(userlevel=user_level, is_active=True)
            stats['by_user_level'][user_level.code] = {
                'name': user_level.name,
                'count': level_users.count(),
                'users': UserListSerializer(level_users, many=True).data
            }
        
        # Statistics by district
        districts = users.filter(is_active=True).values('district__name', 'district__code').distinct()
        for district_data in districts:
            if district_data['district__name']:
                district_users = users.filter(district__code=district_data['district__code'], is_active=True)
                stats['by_district'][district_data['district__code']] = {
                    'name': district_data['district__name'],
                    'count': district_users.count(),
                    'users': UserListSerializer(district_users, many=True).data
                }
        
        # Statistics by section
        sections = users.filter(is_active=True).values('section__name', 'section__code').distinct()
        for section_data in sections:
            if section_data['section__name']:
                section_users = users.filter(section__code=section_data['section__code'], is_active=True)
                stats['by_section'][section_data['section__code']] = {
                    'name': section_data['section__name'],
                    'count': section_users.count(),
                    'users': UserListSerializer(section_users, many=True).data
                }
        
        return Response({
            'section_group': SectionGroupSerializer(section_group).data,
            'statistics': stats
        })


# ---------------------------
# Section Management
# ---------------------------
class SectionViewSet(viewsets.ModelViewSet):
    """ViewSet for Section model with enhanced grouping support"""
    queryset = Section.objects.filter(is_active=True)
    serializer_class = SectionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter sections based on query parameters"""
        queryset = Section.objects.filter(is_active=True).select_related(
            'section_group', 'parent_section'
        ).prefetch_related('subsections', 'users')
        
        # Filter by section group
        section_group = self.request.query_params.get('section_group')
        if section_group:
            queryset = queryset.filter(section_group__code=section_group)
        
        # Filter by parent section
        parent_section = self.request.query_params.get('parent_section')
        if parent_section:
            queryset = queryset.filter(parent_section__code=parent_section)
        
        # Filter by is_combined
        is_combined = self.request.query_params.get('is_combined')
        if is_combined is not None:
            queryset = queryset.filter(is_combined=is_combined.lower() == 'true')
        
        return queryset.order_by('section_group', 'code')
    
    @action(detail=True, methods=['get'])
    def users(self, request, pk=None):
        """Get all users in this section"""
        section = self.get_object()
        users = section.users.filter(is_active=True)
        
        # Apply filters
        userlevel = request.query_params.get('userlevel')
        if userlevel:
            users = users.filter(userlevel__code=userlevel)
        
        district = request.query_params.get('district')
        if district:
            users = users.filter(district__code=district)
        
        serializer = UserListSerializer(users, many=True)
        return Response({
            'section': SectionSerializer(section).data,
            'users': serializer.data,
            'count': users.count()
        })
    
    @action(detail=True, methods=['get'])
    def group_users(self, request, pk=None):
        """Get all users in this section's group (including subsections)"""
        section = self.get_object()
        users = section.get_all_users_in_group()
        
        # Apply filters
        userlevel = request.query_params.get('userlevel')
        if userlevel:
            users = users.filter(userlevel__code=userlevel)
        
        district = request.query_params.get('district')
        if district:
            users = users.filter(district__code=district)
        
        serializer = UserListSerializer(users, many=True)
        return Response({
            'section': SectionSerializer(section).data,
            'group_users': serializer.data,
            'count': users.count()
        })
    
    @action(detail=True, methods=['get'])
    def hierarchy(self, request, pk=None):
        """Get the hierarchy for this section"""
        section = self.get_object()
        hierarchy = section.get_section_hierarchy()
        
        return Response({
            'section': SectionSerializer(section).data,
            'hierarchy': SectionSerializer(hierarchy, many=True).data
        })


# ---------------------------
# User Level Management
# ---------------------------
class UserLevelViewSet(viewsets.ModelViewSet):
    """ViewSet for UserLevel model"""
    queryset = UserLevel.objects.filter(is_active=True)
    serializer_class = UserLevelSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter user levels based on query parameters"""
        queryset = UserLevel.objects.filter(is_active=True)
        
        # Filter by requires_section
        requires_section = self.request.query_params.get('requires_section')
        if requires_section is not None:
            queryset = queryset.filter(requires_section=requires_section.lower() == 'true')
        
        # Filter by requires_district
        requires_district = self.request.query_params.get('requires_district')
        if requires_district is not None:
            queryset = queryset.filter(requires_district=requires_district.lower() == 'true')
        
        return queryset.order_by('code')


# ---------------------------
# District Management
# ---------------------------
class DistrictViewSet(viewsets.ModelViewSet):
    """ViewSet for District model"""
    queryset = District.objects.filter(is_active=True)
    serializer_class = DistrictSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter districts based on query parameters"""
        queryset = District.objects.filter(is_active=True)
        
        # Filter by province
        province = self.request.query_params.get('province')
        if province:
            queryset = queryset.filter(province__icontains=province)
        
        return queryset.order_by('province', 'name')


# ---------------------------
# User Management with Section Grouping
# ---------------------------
class UserViewSet(viewsets.ModelViewSet):
    """ViewSet for User model with enhanced section grouping support"""
    queryset = User.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'create':
            return RegisterSerializer
        elif self.action in ['update', 'partial_update']:
            return UserUpdateSerializer
        elif self.action == 'list':
            return UserListSerializer
        else:
            return UserSerializer
    
    def get_queryset(self):
        """Filter users based on query parameters and permissions"""
        queryset = User.objects.select_related(
            'userlevel', 'section__section_group', 'district'
        ).prefetch_related(
            'profile', 'permissions', 'assignment_history'
        )
        
        # Exclude admin users from regular listings
        if self.action == 'list':
            queryset = queryset.exclude(userlevel__code='Admin')
        
        # Apply filters
        queryset = self.apply_filters(queryset)
        
        return queryset.order_by('-updated_at')
    
    def apply_filters(self, queryset):
        """Apply various filters to the queryset"""
        # Filter by userlevel
        userlevel = self.request.query_params.get('userlevel')
        if userlevel:
            queryset = queryset.filter(userlevel__code=userlevel)
        
        # Filter by section
        section = self.request.query_params.get('section')
        if section:
            queryset = queryset.filter(section__code=section)
        
        # Filter by section group
        section_group = self.request.query_params.get('section_group')
        if section_group:
            queryset = queryset.filter(section__section_group__code=section_group)
        
        # Filter by district
        district = self.request.query_params.get('district')
        if district:
            queryset = queryset.filter(district__code=district)
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            if status_filter == 'active':
                queryset = queryset.filter(is_active=True)
            elif status_filter == 'inactive':
                queryset = queryset.filter(is_active=False)
        
        # Search filter
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) |
                Q(section__name__icontains=search) |
                Q(section__section_group__name__icontains=search) |
                Q(district__name__icontains=search)
            )
        
        return queryset
    
    def perform_create(self, serializer):
        """Create a new user with audit logging"""
        user = serializer.save()
        
        # Log user creation
        log_activity(
            self.request.user if self.request.user.is_authenticated else None,
            "create",
            f"New user registered: {user.email} with auto-generated password",
            request=self.request
        )
        
        # Create notifications
        self.create_new_user_notifications(user)
    
    def perform_update(self, serializer):
        """Update user with audit logging"""
        old_user = self.get_object()
        new_user = serializer.save()
        
        # Log user update
        log_activity(
            self.request.user,
            "update",
            f"Updated user: {new_user.email}",
            request=self.request
        )
        
        # Record assignment history if assignments changed
        self.record_assignment_changes(old_user, new_user)
    
    def create_new_user_notifications(self, new_user):
        """Create notifications for new user creation"""
        division_chiefs = User.objects.filter(userlevel__code='Division Chief', is_active=True)
        
        if new_user.userlevel.code == 'Division Chief':
            for recipient in division_chiefs:
                Notification.objects.create(
                    recipient=recipient,
                    sender=new_user,
                    notification_type='new_user',
                    title='New Division Chief Created',
                    message=f'A new Division Chief ({new_user.email}) has been created.'
                )
        
        elif new_user.userlevel.code == 'Section Chief':
            for recipient in division_chiefs:
                Notification.objects.create(
                    recipient=recipient,
                    sender=new_user,
                    notification_type='new_user',
                    title='New Section Chief Created',
                    message=f'A new Section Chief ({new_user.email}) created for section: {new_user.section.name if new_user.section else "N/A"}.'
                )
        
        elif new_user.userlevel.code == 'Unit Head':
            for recipient in division_chiefs:
                Notification.objects.create(
                    recipient=recipient,
                    sender=new_user,
                    notification_type='new_user',
                    title='New Unit Head Created',
                    message=f'A new Unit Head ({new_user.email}) created for section: {new_user.section.name if new_user.section else "N/A"}.'
                )
            
            section_chiefs = User.objects.filter(
                userlevel__code='Section Chief',
                section=new_user.section,
                is_active=True
            )
            for recipient in section_chiefs:
                Notification.objects.create(
                    recipient=recipient,
                    sender=new_user,
                    notification_type='new_user',
                    title='New Unit Head Created',
                    message=f'Unit Head ({new_user.email}) created in your section: {new_user.section.name if new_user.section else "N/A"}.'
                )
        
        elif new_user.userlevel.code == 'Monitoring Personnel':
            for recipient in division_chiefs:
                Notification.objects.create(
                    recipient=recipient,
                    sender=new_user,
                    notification_type='new_user',
                    title='New Monitoring Personnel Created',
                    message=f'New Monitoring Personnel ({new_user.email}) created for section: {new_user.section.name if new_user.section else "N/A"}.'
                )
            
            section_chiefs = User.objects.filter(
                userlevel__code='Section Chief',
                section=new_user.section,
                is_active=True
            )
            for recipient in section_chiefs:
                Notification.objects.create(
                    recipient=recipient,
                    sender=new_user,
                    notification_type='new_user',
                    title='New Monitoring Personnel Created',
                    message=f'New Monitoring Personnel ({new_user.email}) created in your section: {new_user.section.name if new_user.section else "N/A"}.'
                )
            
            unit_heads = User.objects.filter(
                userlevel__code='Unit Head',
                section=new_user.section,
                is_active=True
            )
            for recipient in unit_heads:
                Notification.objects.create(
                    recipient=recipient,
                    sender=new_user,
                    notification_type='new_user',
                    title='New Monitoring Personnel Created',
                    message=f'New Monitoring Personnel ({new_user.email}) created in your section: {new_user.section.name if new_user.section else "N/A"}.'
                )
        
        elif new_user.userlevel.code in ['Admin', 'Legal Unit']:
            for recipient in division_chiefs:
                Notification.objects.create(
                    recipient=recipient,
                    sender=new_user,
                    notification_type='new_user',
                    title=f'New {new_user.userlevel.name} Created',
                    message=f'A new {new_user.userlevel.name} ({new_user.email}) has been created.'
                )
    
    def record_assignment_changes(self, old_user, new_user):
        """Record assignment changes in history"""
        changes = []
        
        if old_user.userlevel != new_user.userlevel:
            changes.append('userlevel')
        if old_user.section != new_user.section:
            changes.append('section')
        if old_user.district != new_user.district:
            changes.append('district')
        
        if changes:
            UserAssignmentHistory.objects.create(
                user=new_user,
                old_userlevel=old_user.userlevel,
                new_userlevel=new_user.userlevel,
                old_section=old_user.section,
                new_section=new_user.section,
                old_district=old_user.district,
                new_district=new_user.district,
                changed_by=self.request.user,
                reason=f"Updated via API: {', '.join(changes)}"
            )
    
    @action(detail=True, methods=['get'])
    def section_group_users(self, request, pk=None):
        """Get users in the same section group as this user"""
        user = self.get_object()
        users = user.get_section_group_users()
        
        # Apply filters
        userlevel = request.query_params.get('userlevel')
        if userlevel:
            users = users.filter(userlevel__code=userlevel)
        
        district = request.query_params.get('district')
        if district:
            users = users.filter(district__code=district)
        
        serializer = UserListSerializer(users, many=True)
        return Response({
            'user': UserListSerializer(user).data,
            'section_group_users': serializer.data,
            'count': users.count()
        })
    
    @action(detail=True, methods=['get'])
    def section_group_users_by_level(self, request, pk=None):
        """Get users in the same section group grouped by user level"""
        user = self.get_object()
        
        # Get users grouped by level
        users_by_level = {}
        for user_level in UserLevel.objects.filter(is_active=True):
            users = user.get_section_group_users_by_level(user_level.code)
            users_by_level[user_level.code] = {
                'user_level': UserLevelSerializer(user_level).data,
                'users': UserListSerializer(users, many=True).data,
                'count': users.count()
            }
        
        return Response({
            'user': UserListSerializer(user).data,
            'section_group_users_by_level': users_by_level
        })
    
    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """Toggle user active status"""
        user = self.get_object()
        new_active_status = not user.is_active
        
        # Validate user level constraints when activating
        if new_active_status:
            validation_error = self.validate_user_level_constraints_for_activation(user)
            if validation_error:
                return Response(
                    {'detail': validation_error},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        user.is_active = new_active_status
        user.updated_at = timezone.now()
        user.save()
        
        log_activity(
            request.user,
            "update",
            f"Toggled active status for {user.email} → {user.is_active}",
            request=request
        )
        
        return Response({
            'is_active': user.is_active,
            'updated_at': user.updated_at
        }, status=status.HTTP_200_OK)
    
    def validate_user_level_constraints_for_activation(self, user):
        """Validate user level constraints when activating a user"""
        # Check maximum active users for this level
        if user.userlevel.max_active_users is not None:
            active_count = User.objects.filter(
                userlevel=user.userlevel,
                is_active=True
            ).exclude(id=user.id).count()
            
            if active_count >= user.userlevel.max_active_users:
                return f"Maximum {user.userlevel.max_active_users} active {user.userlevel.code} users allowed"
        
        # Check maximum active users per section
        if user.section and user.userlevel.max_active_per_section is not None:
            active_count = User.objects.filter(
                userlevel=user.userlevel,
                section=user.section,
                is_active=True
            ).exclude(id=user.id).count()
            
            if active_count >= user.userlevel.max_active_per_section:
                return f"Maximum {user.userlevel.max_active_per_section} active {user.userlevel.code} users allowed per section"
        
        # Check maximum active users per district
        if user.district and user.userlevel.max_active_per_district is not None:
            active_count = User.objects.filter(
                userlevel=user.userlevel,
                district=user.district,
                is_active=True
            ).exclude(id=user.id).count()
            
            if active_count >= user.userlevel.max_active_per_district:
                return f"Maximum {user.userlevel.max_active_per_district} active {user.userlevel.code} users allowed per district"
        
        return None  # No validation error
    
    @action(detail=True, methods=['post'])
    def assign_district(self, request, pk=None):
        """Assign or update district for a user"""
        user = self.get_object()
        
        # Check if user can assign districts
        if not request.user.can_assign_districts():
            return Response({
                'detail': 'Only Admin, Section Chief, or Unit Head can assign districts.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        district_code = request.data.get('district')
        
        # Validate user type
        if user.userlevel.code not in ['Section Chief', 'Unit Head', 'Monitoring Personnel']:
            return Response({
                'detail': 'Only Section Chief, Unit Head, and Monitoring Personnel can be assigned to districts.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get district object
        district = None
        if district_code:
            try:
                district = District.objects.get(code=district_code, is_active=True)
            except District.DoesNotExist:
                return Response({
                    'detail': f'Invalid district code: {district_code}'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check for existing active user with same role, section, and district
        if district and user.is_active:
            existing = User.objects.filter(
                userlevel=user.userlevel,
                section=user.section,
                district=district,
                is_active=True
            ).exclude(id=user.id).first()
            
            if existing:
                return Response({
                    'detail': f'An active {user.userlevel.code} for {user.section.name if user.section else "N/A"} in {district.name} already exists: {existing.email}'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update district
        old_district = user.district
        user.district = district
        user.updated_at = timezone.now()
        user.save()
        
        # Record assignment history
        if old_district != district:
            UserAssignmentHistory.objects.create(
                user=user,
                old_district=old_district,
                new_district=district,
                changed_by=request.user,
                reason="District assignment updated"
            )
        
        log_activity(
            request.user,
            "update",
            f"Assigned district {district.name if district else 'None'} to {user.email}",
            request=request
        )
        
        return Response({
            'message': 'District assigned successfully',
            'user': UserSerializer(user).data
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def assignment_history(self, request, pk=None):
        """Get assignment history for a user"""
        user = self.get_object()
        history = user.assignment_history.all()
        serializer = UserAssignmentHistorySerializer(history, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def permissions(self, request, pk=None):
        """Get permissions for a user"""
        user = self.get_object()
        permissions = user.permissions.all()
        serializer = UserPermissionSerializer(permissions, many=True)
        return Response(serializer.data)


# ---------------------------
# User Profile Management
# ---------------------------
class UserProfileViewSet(viewsets.ModelViewSet):
    """ViewSet for UserProfile model"""
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter profiles based on user permissions"""
        queryset = UserProfile.objects.select_related('user')
        
        # Users can only see their own profile unless they're admin
        if not self.request.user.is_superuser:
            queryset = queryset.filter(user=self.request.user)
        
        return queryset


# ---------------------------
# Authentication Views
# ---------------------------
class RegisterView(APIView):
    """User registration view with enhanced section grouping"""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        data = request.data.copy()
        if "password" in data:
            data.pop("password")  # prevent frontend from setting password
        
        serializer = RegisterSerializer(data=data)
        if serializer.is_valid():
            user = serializer.save()
            
            refresh = RefreshToken.for_user(user)
            data = {
                "user": UserSerializer(user).data,
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            }
            return Response(data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProfileView(APIView):
    """User profile view"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        return Response(UserSerializer(request.user).data)


# ---------------------------
# Section Grouping Utility Views
# ---------------------------
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def users_by_section_group(request):
    """Get users grouped by section group"""
    section_groups = SectionGroup.objects.filter(is_active=True).prefetch_related(
        'sections__users'
    )
    
    result = {}
    for group in section_groups:
        users = group.get_all_users()
        
        # Apply filters
        userlevel = request.query_params.get('userlevel')
        if userlevel:
            users = users.filter(userlevel__code=userlevel)
        
        district = request.query_params.get('district')
        if district:
            users = users.filter(district__code=district)
        
        result[group.code] = {
            'section_group': SectionGroupSerializer(group).data,
            'users': UserListSerializer(users, many=True).data,
            'count': users.count()
        }
    
    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def users_by_section_group_and_level(request):
    """Get users grouped by section group and user level"""
    section_groups = SectionGroup.objects.filter(is_active=True)
    
    result = {}
    for group in section_groups:
        group_data = {
            'section_group': SectionGroupSerializer(group).data,
            'users_by_level': {}
        }
        
        for user_level in UserLevel.objects.filter(is_active=True):
            users = group.get_all_users().filter(userlevel=user_level)
            group_data['users_by_level'][user_level.code] = {
                'user_level': UserLevelSerializer(user_level).data,
                'users': UserListSerializer(users, many=True).data,
                'count': users.count()
            }
        
        result[group.code] = group_data
    
    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def section_group_statistics(request):
    """Get statistics for all section groups"""
    section_groups = SectionGroup.objects.filter(is_active=True)
    
    statistics = []
    for group in section_groups:
        users = group.get_all_users()
        
        stats = {
            'section_group': SectionGroupSerializer(group).data,
            'total_users': users.count(),
            'active_users': users.filter(is_active=True).count(),
            'inactive_users': users.filter(is_active=False).count(),
            'by_user_level': {},
            'by_district': {},
            'by_section': {}
        }
        
        # Statistics by user level
        for user_level in UserLevel.objects.filter(is_active=True):
            level_users = users.filter(userlevel=user_level, is_active=True)
            stats['by_user_level'][user_level.code] = {
                'name': user_level.name,
                'count': level_users.count()
            }
        
        # Statistics by district
        districts = users.filter(is_active=True).values('district__name', 'district__code').distinct()
        for district_data in districts:
            if district_data['district__name']:
                district_users = users.filter(district__code=district_data['district__code'], is_active=True)
                stats['by_district'][district_data['district__code']] = {
                    'name': district_data['district__name'],
                    'count': district_users.count()
                }
        
        # Statistics by section
        sections = users.filter(is_active=True).values('section__name', 'section__code').distinct()
        for section_data in sections:
            if section_data['section__name']:
                section_users = users.filter(section__code=section_data['section__code'], is_active=True)
                stats['by_section'][section_data['section__code']] = {
                    'name': section_data['section__name'],
                    'count': section_users.count()
                }
        
        statistics.append(stats)
    
    return Response(statistics)


# ---------------------------
# Password Management (same as before)
# ---------------------------
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """Change user password"""
    user = request.user
    old_password = request.data.get('old_password')
    new_password = request.data.get('new_password')
    
    if not old_password or not new_password:
        return Response({'detail': 'Both old and new password are required.'}, status=400)
    
    if not user.check_password(old_password):
        return Response({'detail': 'Old password is incorrect.'}, status=400)
    
    # Don't allow reusing the same password
    if new_password == old_password:
        return Response({'detail': 'New password cannot be the same as old password.'}, status=400)
    
    user.set_password(new_password)
    user.must_change_password = False
    user.is_first_login = False
    user.updated_at = timezone.now()
    user.save()
    
    log_activity(user, "update", f"Password changed for {user.email}", request=request)
    
    return Response({
        'detail': 'Password changed successfully.',
        'updated_at': user.updated_at
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def first_time_change_password(request):
    """First time password change"""
    user = request.user
    new_password = request.data.get('new_password')
    
    if not new_password:
        return Response({'detail': 'New password is required.'}, status=400)
    
    user.set_password(new_password)
    user.must_change_password = False
    user.is_first_login = False
    user.updated_at = timezone.now()
    user.save()
    
    log_activity(user, "update", f"First-time password set for {user.email}", request=request)
    
    return Response({
        'detail': 'Password changed successfully.',
        'updated_at': user.updated_at
    })


# ---------------------------
# OTP Management (same as before)
# ---------------------------
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def send_otp(request):
    """Send OTP for password reset"""
    email = request.data.get('email')
    if not email:
        return Response({'detail': 'Email is required.'}, status=400)
    
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({'detail': 'User with this email does not exist.'}, status=404)
    
    otp = generate_otp(email)
    if send_otp_email(email, otp):
        return Response({'detail': 'OTP sent to your email.'}, status=200)
    return Response({'detail': 'Failed to send OTP email.'}, status=500)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def verify_otp_view(request):
    """Verify OTP"""
    email = request.data.get('email')
    otp = request.data.get('otp')
    
    if not email or not otp:
        return Response({'detail': 'Email and OTP are required.'}, status=400)
    
    if verify_otp(email, otp):
        return Response({'detail': 'OTP verified successfully.'}, status=200)
    return Response({'detail': 'Invalid or expired OTP.'}, status=400)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def reset_password_with_otp(request):
    """Reset password using OTP"""
    email = request.data.get('email')
    otp = request.data.get('otp')
    new_password = request.data.get('new_password')
    
    if not email or not otp or not new_password:
        return Response({'detail': 'Email, OTP and new password are required.'}, status=400)
    
    if not verify_otp(email, otp):
        return Response({'detail': 'Invalid or expired OTP.'}, status=400)
    
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({'detail': 'User with this email does not exist.'}, status=404)
    
    user.set_password(new_password)
    user.must_change_password = False
    user.is_first_login = False
    user.updated_at = timezone.now()
    user.save()
    
    cache.delete(f"otp_{email}")
    
    log_activity(user, "update", f"Password reset via OTP for {user.email}", request=request)
    
    return Response({
        'detail': 'Password reset successfully.',
        'updated_at': user.updated_at
    }, status=200)


# ---------------------------
# Search and Utility Views
# ---------------------------
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_search(request):
    """Search users with section grouping support"""
    query = request.GET.get('q', '').strip()
    
    if not query or len(query) < 2:
        return Response({'results': [], 'count': 0})
    
    users = User.objects.filter(
        Q(first_name__icontains=query) |
        Q(middle_name__icontains=query) |
        Q(last_name__icontains=query) |
        Q(email__icontains=query) |
        Q(userlevel__name__icontains=query) |
        Q(section__name__icontains=query) |
        Q(section__section_group__name__icontains=query)
    ).exclude(userlevel__code='Admin')
    
    serializer = UserListSerializer(users, many=True)
    return Response({
        'results': serializer.data,
        'count': users.count()
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def district_users_list(request):
    """Get users filtered by role and district for district management"""
    # Get filter parameters
    userlevel = request.query_params.get('userlevel')
    district = request.query_params.get('district')
    section = request.query_params.get('section')
    section_group = request.query_params.get('section_group')
    
    # Filter only Section Chief, Unit Head, and Monitoring Personnel
    queryset = User.objects.filter(
        userlevel__code__in=['Section Chief', 'Unit Head', 'Monitoring Personnel']
    ).select_related('userlevel', 'section__section_group', 'district').order_by(
        'district__name', 'section__section_group__name', 'section__name', 'userlevel__name', 'last_name'
    )
    
    # Apply filters if provided
    if userlevel:
        queryset = queryset.filter(userlevel__code=userlevel)
    if district:
        queryset = queryset.filter(district__code=district)
    if section:
        queryset = queryset.filter(section__code=section)
    if section_group:
        queryset = queryset.filter(section__section_group__code=section_group)
    
    serializer = UserListSerializer(queryset, many=True)
    return Response({
        'results': serializer.data,
        'count': queryset.count()
    })


# ---------------------------
# Logout
# ---------------------------
class LogoutView(APIView):
    """User logout view"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response(
                    {"detail": "Refresh token required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"detail": "Successfully logged out."}, status=status.HTTP_200_OK)
        except Exception:
            return Response({"detail": "Invalid token."}, status=status.HTTP_400_BAD_REQUEST)
