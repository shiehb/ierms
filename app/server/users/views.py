import math

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions, generics
from .serializers import RegisterSerializer, UserSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from django.conf import settings
from django.contrib.auth import get_user_model, authenticate
from .utils.otp_utils import generate_otp, verify_otp, send_otp_email
from .utils.email_utils import send_account_activated_email, send_account_deactivated_email
from django.core.cache import cache
from django.utils import timezone
from django.db.models import Q
from django.utils.dateparse import parse_datetime
from core.settings import generate_secure_password

# Notifications
from notifications.models import Notification

# Audit logging
from audit.constants import AUDIT_ACTIONS, AUDIT_MODULES
from audit.utils import log_activity

User = get_user_model()


# ---------------------------
# Authentication
# ---------------------------
class LoginView(APIView):
    """
    Custom login view with account lockout error handling
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')

        if not email or not password:
            log_activity(
                None,
                AUDIT_ACTIONS["LOGIN"],
                module=AUDIT_MODULES["AUTH"],
                description="Login attempt with missing credentials",
                metadata={
                    "email": email,
                    "status": "failed",
                    "reason": "missing_credentials",
                },
                request=request,
            )
            return Response({
                'error': 'Email and password are required.',
                'error_code': 'MISSING_CREDENTIALS'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
            
            # Check if account is locked
            if user.is_account_currently_locked():
                remaining_time = self._get_remaining_lockout_time(user)
                lockout_duration = user.lockout_duration_minutes
                log_activity(
                    user,
                    AUDIT_ACTIONS["LOGIN"],
                    module=AUDIT_MODULES["AUTH"],
                    description=f"Login blocked for locked account {email}",
                    metadata={
                        "email": email,
                        "status": "failed",
                        "reason": "account_locked",
                        "remaining_minutes": remaining_time,
                        "lockout_duration_minutes": lockout_duration,
                        "unlock_at": user.account_locked_until.isoformat() if user.account_locked_until else None,
                    },
                    request=request,
                )
                return Response({
                    'error': f'Account locked. Try again in {remaining_time} minutes.',
                    'error_code': 'ACCOUNT_LOCKED',
                    'details': {
                        'remaining_minutes': remaining_time,
                        'unlock_at': user.account_locked_until.isoformat() if user.account_locked_until else None,
                        'lockout_duration_minutes': lockout_duration,
                    }
                }, status=status.HTTP_423_LOCKED)
            
            # Authenticate user
            user = authenticate(request, email=email, password=password)
            
            if user is None:
                # Wrong password - gather updated attempt data (signal already incremented)
                db_user = None
                details = None
                try:
                    db_user = User.objects.get(email=email)

                    if db_user.is_account_locked:
                        remaining_time = self._get_remaining_lockout_time(db_user)
                        lockout_duration = db_user.lockout_duration_minutes
                        log_activity(
                            db_user,
                            AUDIT_ACTIONS["LOGIN"],
                            module=AUDIT_MODULES["AUTH"],
                            description=f"Login blocked for locked account {email}",
                            metadata={
                                "email": email,
                                "status": "failed",
                                "reason": "account_locked",
                                "remaining_minutes": remaining_time,
                                "lockout_duration_minutes": lockout_duration,
                                "unlock_at": db_user.account_locked_until.isoformat() if db_user.account_locked_until else None,
                            },
                            request=request,
                        )
                        return Response({
                            'error': f'Account locked. Try again in {remaining_time} minutes.',
                            'error_code': 'ACCOUNT_LOCKED',
                            'details': {
                                'remaining_minutes': remaining_time,
                                'unlock_at': db_user.account_locked_until.isoformat() if db_user.account_locked_until else None,
                                'lockout_duration_minutes': lockout_duration,
                            }
                        }, status=status.HTTP_423_LOCKED)

                    remaining_attempts = max(db_user.max_failed_login_attempts - db_user.failed_login_attempts, 0)
                    warning_window = getattr(settings, 'LOGIN_FINAL_ATTEMPTS_WARNING', 3)
                    details = {
                        'failed_attempts': db_user.failed_login_attempts,
                        'remaining_attempts': remaining_attempts,
                        'max_attempts': db_user.max_failed_login_attempts,
                        'is_last_attempt_window': remaining_attempts <= warning_window,
                        'lockout_duration_minutes': db_user.lockout_duration_minutes,
                    }
                except User.DoesNotExist:
                    details = None
                
                log_activity(
                    None,
                    AUDIT_ACTIONS["LOGIN"],
                    module=AUDIT_MODULES["AUTH"],
                    description=f"Invalid login attempt for {email}",
                    metadata={
                        "email": email,
                        "status": "failed",
                        "reason": "invalid_credentials",
                        "failed_attempts": details.get('failed_attempts') if details else None,
                        "remaining_attempts": details.get('remaining_attempts') if details else None,
                        "lockout_duration_minutes": details.get('lockout_duration_minutes') if details else None,
                    },
                    request=request,
                )
                response_payload = {
                    'error': 'Invalid email or password.',
                    'error_code': 'INVALID_CREDENTIALS'
                }
                if details and db_user:
                    if db_user.account_locked_until:
                        details['unlock_at'] = db_user.account_locked_until.isoformat()
                    response_payload['details'] = details
                return Response(response_payload, status=status.HTTP_401_UNAUTHORIZED)
            
            # Check if user is active
            if not user.is_active:
                log_activity(
                    user,
                    AUDIT_ACTIONS["LOGIN"],
                    module=AUDIT_MODULES["AUTH"],
                    description=f"Login blocked for deactivated user {email}",
                    metadata={
                        "email": email,
                        "status": "failed",
                        "reason": "account_deactivated",
                    },
                    request=request,
                )
                return Response({
                    'error': 'Account deactivated. Contact administrator.',
                    'error_code': 'ACCOUNT_DEACTIVATED'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Reset failed login attempts on successful login
            user.reset_failed_logins()
            
            # Update last_login timestamp
            user.last_login = timezone.now()
            user.save(update_fields=['last_login'])
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            access_token = refresh.access_token
            
            log_activity(
                user,
                AUDIT_ACTIONS["LOGIN"],
                module=AUDIT_MODULES["AUTH"],
                description=f"{user.email} logged in",
                metadata={
                    "user_id": user.id,
                    "email": user.email,
                    "status": "success",
                },
                request=request,
            )
            return Response({
                'success': True,
                'message': 'Login successful',
                'user': UserSerializer(user).data,
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(access_token),
                }
            }, status=status.HTTP_200_OK)
            
        except User.DoesNotExist:
            log_activity(
                None,
                AUDIT_ACTIONS["LOGIN"],
                module=AUDIT_MODULES["AUTH"],
                description=f"Invalid login attempt for unknown user {email}",
                metadata={
                    "email": email,
                    "status": "failed",
                    "reason": "invalid_credentials",
                },
                request=request,
            )
            return Response({
                'error': 'Invalid email or password.',
                'error_code': 'INVALID_CREDENTIALS'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        except Exception as e:
            log_activity(
                None,
                AUDIT_ACTIONS["LOGIN"],
                module=AUDIT_MODULES["AUTH"],
                description=f"Login error for {email}",
                metadata={
                    "email": email,
                    "status": "failed",
                    "reason": "exception",
                    "error": str(e),
                },
                request=request,
            )
            return Response({
                'error': 'Login failed. Please try again.',
                'error_code': 'LOGIN_ERROR'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _get_remaining_lockout_time(self, user):
        """Calculate remaining lockout time in minutes"""
        if not user.account_locked_until:
            return 0
        
        now = timezone.now()
        if now >= user.account_locked_until:
            return 0
        
        delta = user.account_locked_until - now
        return max(1, math.ceil(delta.total_seconds() / 60))


# ---------------------------
# Registration
# ---------------------------
class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        # Validate email configuration from environment variables
        import os
        
        email_host = os.getenv("EMAIL_HOST_USER")
        email_password = os.getenv("EMAIL_HOST_PASSWORD")
        default_from_email = os.getenv("DEFAULT_FROM_EMAIL")
        
        # Check if email settings are configured
        if not all([email_host, email_password, default_from_email]):
            return Response({
                'detail': 'Email configuration is incomplete. Please contact your system administrator to configure email settings.',
                'error_code': 'EMAIL_NOT_CONFIGURED'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        data = request.data.copy()
        if "password" in data:
            data.pop("password")  # prevent frontend from setting password

        serializer = RegisterSerializer(data=data, context={'request': request})
        if serializer.is_valid():
            user = serializer.save()

            # 📌 Log user creation
            log_activity(
                request.user if request.user.is_authenticated else None,
                AUDIT_ACTIONS["CREATE"],
                module=AUDIT_MODULES["USERS"],
                description=f"{(request.user.email if request.user.is_authenticated else 'System')} registered user {user.email}",
                metadata={
                    "entity_name": user.email,
                    "entity_id": user.id,
                    "role": user.userlevel,
                    "status": "success",
                },
                request=request,
            )

            self.create_new_user_notifications(user)

            refresh = RefreshToken.for_user(user)
            data = {
                "user": UserSerializer(user).data,
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            }
            return Response(data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def create_new_user_notifications(self, new_user):
        division_chiefs = User.objects.filter(userlevel="Division Chief", is_active=True)

        if new_user.userlevel == "Division Chief":
            for recipient in division_chiefs:
                Notification.objects.create(
                    recipient=recipient,
                    sender=new_user,
                    notification_type='new_user',
                    title='New Division Chief Created',
                    message=f'A new Division Chief ({new_user.email}) has been created.'
                )

        elif new_user.userlevel == "Section Chief":
            for recipient in division_chiefs:
                Notification.objects.create(
                    recipient=recipient,
                    sender=new_user,
                    notification_type='new_user',
                    title='New Section Chief Created',
                    message=f'A new Section Chief ({new_user.email}) created for section: {new_user.section}.'
                )

        elif new_user.userlevel == "Unit Head":
            for recipient in division_chiefs:
                Notification.objects.create(
                    recipient=recipient,
                    sender=new_user,
                    notification_type='new_user',
                    title='New Unit Head Created',
                    message=f'A new Unit Head ({new_user.email}) created for section: {new_user.section}.'
                )
            section_chiefs = User.objects.filter(userlevel="Section Chief", section=new_user.section, is_active=True)
            for recipient in section_chiefs:
                Notification.objects.create(
                    recipient=recipient,
                    sender=new_user,
                    notification_type='new_user',
                    title='New Unit Head Created',
                    message=f'Unit Head ({new_user.email}) created in your section: {new_user.section}.'
                )

        elif new_user.userlevel == "Monitoring Personnel":
            for recipient in division_chiefs:
                Notification.objects.create(
                    recipient=recipient,
                    sender=new_user,
                    notification_type='new_user',
                    title='New Monitoring Personnel Created',
                    message=f'New Monitoring Personnel ({new_user.email}) created for section: {new_user.section}.'
                )
            section_chiefs = User.objects.filter(userlevel="Section Chief", section=new_user.section, is_active=True)
            for recipient in section_chiefs:
                Notification.objects.create(
                    recipient=recipient,
                    sender=new_user,
                    notification_type='new_user',
                    title='New Monitoring Personnel Created',
                    message=f'New Monitoring Personnel ({new_user.email}) created in your section: {new_user.section}.'
                )
            unit_heads = User.objects.filter(userlevel="Unit Head", section=new_user.section, is_active=True)
            for recipient in unit_heads:
                Notification.objects.create(
                    recipient=recipient,
                    sender=new_user,
                    notification_type='new_user',
                    title='New Monitoring Personnel Created',
                    message=f'New Monitoring Personnel ({new_user.email}) created in your section: {new_user.section}.'
                )

        elif new_user.userlevel in ["Admin", "Legal Unit"]:
            for recipient in division_chiefs:
                Notification.objects.create(
                    recipient=recipient,
                    sender=new_user,
                    notification_type='new_user',
                    title=f'New {new_user.userlevel} Created',
                    message=f'A new {new_user.userlevel} ({new_user.email}) has been created.'
                )


# ---------------------------
# Profile
# ---------------------------
class ProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user, context={'request': request})
        return Response(serializer.data)


# ---------------------------
# List Users
# ---------------------------
class UserListView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return User.objects.exclude(userlevel="Admin").order_by('-updated_at')
    
    def list(self, request, *args, **kwargs):
        # Get pagination parameters
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 10))
        
        # Get filtered queryset
        queryset = self.get_queryset()
        
        # Apply search filter if provided
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) |
                Q(section__icontains=search)
            )
        
        # Apply role filter if provided
        role = request.query_params.get('role')
        if role:
            queryset = queryset.filter(userlevel=role)
        
        # Apply status filter if provided
        status = request.query_params.get('status')
        if status:
            if status == 'active':
                queryset = queryset.filter(is_active=True)
            elif status == 'inactive':
                queryset = queryset.filter(is_active=False)
        
        # Calculate pagination
        total_count = queryset.count()
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        
        # Apply pagination
        users = queryset[start_index:end_index]
        
        # Serialize data
        serializer = self.get_serializer(users, many=True)
        
        # Return paginated response
        return Response({
            'count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size,
            'results': serializer.data
        })


# ---------------------------
# Update User
# ---------------------------
class UserUpdateView(generics.RetrieveUpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"

    def perform_update(self, serializer):
        # Get the original user instance before update
        original_user = self.get_object()
        original_email = original_user.email
        original_avatar = original_user.avatar  # Store old avatar path
        
        # Check if email is being changed
        new_email = serializer.validated_data.get('email', original_email)
        email_changed = new_email != original_email
        
        # Check if avatar is being updated
        new_avatar = serializer.validated_data.get('avatar')
        avatar_changed = new_avatar is not None
        
        # Save the user with updated data (this will optimize the avatar if provided)
        user = serializer.save()
        
        # Delete old avatar file if avatar was updated
        if avatar_changed and original_avatar:
            try:
                # Delete the old avatar file from storage
                original_avatar.delete(save=False)
            except Exception as e:
                # Log error but don't fail the update
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to delete old avatar file for user {user.id}: {str(e)}")
        
        # If email changed, generate new password and send credentials
        if email_changed:
            from .utils.email_utils import send_welcome_email
            
            # Generate new password
            new_password = generate_secure_password()
            
            # Set the new password
            user.set_password(new_password)
            
            # Set flags for forced password change
            user.must_change_password = True
            user.is_first_login = True
            
            # Save the user with new password and flags
            user.save()
            
            # Send email with new credentials
            try:
                send_welcome_email(user, new_password)
                log_activity(
                    self.request.user,
                    AUDIT_ACTIONS["UPDATE"],
                    module=AUDIT_MODULES["USERS"],
                    description=f"{self.request.user.email} changed email for {original_email} to {user.email}",
                    metadata={
                        "entity_name": user.email,
                        "entity_id": user.id,
                        "before": {"email": original_email},
                        "after": {"email": user.email},
                        "status": "success",
                    },
                    request=self.request,
                )
            except Exception as e:
                # Log the error but don't fail the update
                log_activity(
                    self.request.user,
                    AUDIT_ACTIONS["SYSTEM"],
                    module=AUDIT_MODULES["USERS"],
                    description=f"{self.request.user.email} updated {user.email} but failed to send welcome email",
                    metadata={
                        "entity_name": user.email,
                        "entity_id": user.id,
                        "status": "failed",
                        "error": str(e),
                    },
                    request=self.request,
                )
        else:
            log_activity(
                self.request.user,
                AUDIT_ACTIONS["UPDATE"],
                module=AUDIT_MODULES["USERS"],
                description=f"{self.request.user.email} updated user {user.email}",
                metadata={
                    "entity_name": user.email,
                    "entity_id": user.id,
                    "status": "success",
                },
                request=self.request,
            )


# ---------------------------
# Logout
# ---------------------------
class LogoutView(APIView):
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
            # ⚠️ No log_activity here → logout handled by signal
            return Response({"detail": "Successfully logged out."}, status=status.HTTP_200_OK)
        except Exception:
            return Response({"detail": "Invalid token."}, status=status.HTTP_400_BAD_REQUEST)


# ---------------------------
# Toggle Active
# ---------------------------
@api_view(['POST'])
@permission_classes([IsAdminUser])
def toggle_user_active(request, pk):
    try:
        user = User.objects.get(pk=pk)
        new_active_status = not user.is_active
        
        # When activating, check for existing active users and deactivate them automatically
        if new_active_status:
            existing_active_user = get_existing_active_user_for_role(user)
            if existing_active_user:
                # Deactivate the existing active user
                existing_active_user.is_active = False
                existing_active_user.updated_at = timezone.now()
                existing_active_user.save()
                
                # Log the automatic deactivation
                log_activity(
                    request.user,
                    AUDIT_ACTIONS["UPDATE"],
                    module=AUDIT_MODULES["USERS"],
                    description=f"{request.user.email} automatically deactivated user {existing_active_user.email} to activate {user.email}",
                    metadata={
                        "entity_name": existing_active_user.email,
                        "entity_id": existing_active_user.id,
                        "status": "success",
                        "before": {"is_active": True},
                        "after": {"is_active": False},
                        "reason": f"Auto-deactivated to allow activation of {user.email} ({user.userlevel})",
                    },
                    request=request,
                )
                
                # Send deactivation email to the previously active user
                try:
                    ip_address = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', 'Unknown'))
                    if ',' in ip_address:
                        ip_address = ip_address.split(',')[0].strip()
                    
                    user_agent = request.META.get('HTTP_USER_AGENT', '')
                    
                    send_account_deactivated_email(
                        user=existing_active_user,
                        deactivated_by=request.user,
                        ip_address=ip_address,
                        user_agent=user_agent
                    )
                except Exception as e:
                    # Log the error but don't fail the request
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to send deactivation email to {existing_active_user.email}: {str(e)}")
        
        # Activate/deactivate the target user
        user.is_active = new_active_status
        user.updated_at = timezone.now()
        user.save()

        log_activity(
            request.user,
            AUDIT_ACTIONS["UPDATE"],
            module=AUDIT_MODULES["USERS"],
            description=f"{request.user.email} {'activated' if new_active_status else 'deactivated'} user {user.email}",
            metadata={
                "entity_name": user.email,
                "entity_id": user.id,
                "status": "success",
                "before": {"is_active": not new_active_status},
                "after": {"is_active": new_active_status},
            },
            request=request,
        )

        # Send email notification to the user
        try:
            # Get IP address and User-Agent from request
            ip_address = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', 'Unknown'))
            if ',' in ip_address:
                ip_address = ip_address.split(',')[0].strip()
            
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            
            # Send appropriate email based on activation status
            if new_active_status:
                send_account_activated_email(
                    user=user,
                    activated_by=request.user,
                    ip_address=ip_address,
                    user_agent=user_agent
                )
            else:
                send_account_deactivated_email(
                    user=user,
                    deactivated_by=request.user,
                    ip_address=ip_address,
                    user_agent=user_agent
                )
        except Exception as e:
            # Log the error but don't fail the request
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send account status email to {user.email}: {str(e)}")

        return Response({
            'is_active': user.is_active,
            'updated_at': user.updated_at
        }, status=status.HTTP_200_OK)
    except User.DoesNotExist:
        return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

def get_existing_active_user_for_role(user):
    """Get existing active user for roles that only allow one active user at a time.
    Returns the existing active user object if found, None otherwise.
    """
    from django.db.models import Q
    
    # Division Chief: Only one active
    if user.userlevel == "Division Chief":
        existing_active = User.objects.filter(
            userlevel="Division Chief", 
            is_active=True
        ).exclude(id=user.id).first()
        if existing_active:
            return existing_active
    
    # Section Chief: Only one active per law (section)
    elif user.userlevel == "Section Chief":
        if user.section:
            existing_active = User.objects.filter(
                userlevel="Section Chief", 
                section=user.section, 
                is_active=True
            ).exclude(id=user.id).first()
            if existing_active:
                return existing_active
    
    # Unit Head: Only one active per law (section)
    elif user.userlevel == "Unit Head":
        if user.section:
            existing_active = User.objects.filter(
                userlevel="Unit Head", 
                section=user.section, 
                is_active=True
            ).exclude(id=user.id).first()
            if existing_active:
                return existing_active
    
    # Legal Unit and Monitoring Personnel: Multiple allowed (no validation needed)
    
    return None  # No existing active user found


# ---------------------------
# Change Password
# ---------------------------
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    user = request.user
    old_password = request.data.get('old_password')
    new_password = request.data.get('new_password')

    if not old_password or not new_password:
        return Response({'detail': 'Both old and new password are required.'}, status=400)

    if not user.check_password(old_password):
        return Response({'detail': 'Old password is incorrect.'}, status=400)

    # Don't allow reusing the same password (check against entered old password)
    if new_password == old_password:
        return Response({'detail': 'New password cannot be the same as old password.'}, status=400)

    # Also check against the actual stored password
    if user.check_password(new_password):
        return Response({'detail': 'New password cannot be the same as your current password.'}, status=400)

    user.set_password(new_password)
    user.must_change_password = False
    user.is_first_login = False
    user.updated_at = timezone.now()
    user.save()

    log_activity(
        user,
        AUDIT_ACTIONS["UPDATE"],
        module=AUDIT_MODULES["AUTH"],
        description=f"{user.email} changed password",
        metadata={
            "user_id": user.id,
            "status": "success",
            "operation": "change_password",
        },
        request=request,
    )

    return Response({
        'detail': 'Password changed successfully.',
        'updated_at': user.updated_at
    })


# ---------------------------
# First Time Change Password
# ---------------------------
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def first_time_change_password(request):
    user = request.user
    old_password = request.data.get('old_password')
    new_password = request.data.get('new_password')

    if not old_password or not new_password:
        return Response({'detail': 'Both old and new password are required.'}, status=400)

    if not user.check_password(old_password):
        return Response({'detail': 'Old password is incorrect.'}, status=400)

    # Don't allow reusing the same password (check against entered old password)
    if new_password == old_password:
        return Response({'detail': 'New password cannot be the same as old password.'}, status=400)

    # Also check against the actual stored password
    if user.check_password(new_password):
        return Response({'detail': 'New password cannot be the same as your current password.'}, status=400)

    user.set_password(new_password)
    user.must_change_password = False
    user.is_first_login = False
    user.updated_at = timezone.now()
    user.save()

    log_activity(
        user,
        AUDIT_ACTIONS["UPDATE"],
        module=AUDIT_MODULES["AUTH"],
        description=f"{user.email} completed first-time password setup",
        metadata={
            "user_id": user.id,
            "status": "success",
            "operation": "first_time_change_password",
        },
        request=request,
    )

    return Response({
        'detail': 'Password changed successfully.',
        'updated_at': user.updated_at
    })


# ---------------------------
# OTP
# ---------------------------
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def send_otp(request):
    email = request.data.get('email')
    if not email:
        return Response({'detail': 'Email is required.'}, status=400)

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({'detail': 'User with this email does not exist.'}, status=404)

    # Get client IP address
    ip_address = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', 'Unknown'))
    
    otp = generate_otp(email)
    if send_otp_email(email, otp, user=user, ip_address=ip_address):
        return Response({'detail': 'OTP sent to your email.'}, status=200)
    return Response({'detail': 'Failed to send OTP email.'}, status=500)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def verify_otp_view(request):
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

    # Check if new password is same as current password
    if user.check_password(new_password):
        return Response({
            'detail': 'New password cannot be the same as your current password. Please choose a different password.'
        }, status=400)

    user.set_password(new_password)
    user.must_change_password = False
    user.is_first_login = False
    user.updated_at = timezone.now()
    user.save()

    cache.delete(f"otp_{email}")

    log_activity(
        user,
        AUDIT_ACTIONS["UPDATE"],
        module=AUDIT_MODULES["AUTH"],
        description=f"{user.email} reset password via OTP",
        metadata={
            "user_id": user.id,
            "status": "success",
            "operation": "reset_password_otp",
        },
        request=request,
    )

    return Response({
        'detail': 'Password reset successfully.',
        'updated_at': user.updated_at
    }, status=200)

# Add this to your users views
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_search(request):
    query = request.GET.get('q', '').strip()
    
    if not query or len(query) < 2:
        return Response({'results': [], 'count': 0})
    
    users = User.objects.filter(
        Q(first_name__icontains=query) |
        Q(middle_name__icontains=query) |
        Q(last_name__icontains=query) |
        Q(email__icontains=query) |
        Q(userlevel__icontains=query)
    ).exclude(userlevel="Admin")
    
    serializer = UserSerializer(users, many=True)
    return Response({
        'results': serializer.data,
        'count': users.count()
    })