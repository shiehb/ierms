from rest_framework import serializers
from .models import User
from .utils.image_utils import optimize_avatar
from .signals import user_created_with_password
from core.settings import generate_secure_password
import logging

logger = logging.getLogger(__name__)

class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            'id',
            'email',
            'first_name',
            'middle_name',
            'last_name',
            'userlevel',
            'section',
            'avatar',
            'date_joined',
        )
        read_only_fields = ('id', 'date_joined')

    def validate(self, data):
        userlevel = data.get('userlevel')
        section = data.get('section')
        
        # For Division Chief, Legal Unit, and Admin - section is not required
        if userlevel in ["Division Chief", "Legal Unit", "Admin"]:
            if section:
                raise serializers.ValidationError({
                    "section": "Section should not be provided for Division Chief, Legal Unit, or Admin users."
                })
            data["section"] = None
        
        # For Section Chief, Unit Head, and Monitoring Personnel - section is required
        elif userlevel in ["Section Chief", "Unit Head", "Monitoring Personnel"]:
            if not section:
                raise serializers.ValidationError({
                    "section": "This field is required for Section Chief, Unit Head, and Monitoring Personnel users."
                })
        
        # Validate user level constraints
        self.validate_user_level_constraints(userlevel, section)

        return data

    def validate_user_level_constraints(self, userlevel, section):
        """Validate user level constraints based on business rules"""
        from .models import User
        
        # Division Chief, Section Chief, and Unit Head: Auto-deactivate existing users in create()
        # No validation errors - they will be auto-deactivated when new user is created
        
        # Monitoring Personnel: Only one active per law
        if userlevel == "Monitoring Personnel":
            if section:
                existing_active = User.objects.filter(
                    userlevel="Monitoring Personnel", 
                    section=section, 
                    is_active=True
                ).first()
                if existing_active:
                    raise serializers.ValidationError({
                        "userlevel": f"Only one active Monitoring Personnel is allowed per law. Currently active for {section}: {existing_active.email}"
                    })
        
        # Legal Unit: Multiple allowed (no validation needed)

    def create(self, validated_data):
        # Extract avatar if present
        avatar = validated_data.pop('avatar', None)
        request = self.context.get('request')
        
        # Generate password
        generated_password = SystemConfiguration.generate_default_password()
        
        # Auto-deactivate existing users for Division Chief, Section Chief, and Unit Head
        userlevel = validated_data.get('userlevel')
        section = validated_data.get('section')
        
        if userlevel == "Division Chief":
            old_users = User.objects.filter(userlevel="Division Chief", is_active=True)
            for old_user in old_users:
                old_user.is_active = False
                old_user.save()
                try:
                    from audit.utils import log_activity
                    from audit.constants import AUDIT_ACTIONS, AUDIT_MODULES
                    log_activity(
                        request.user if request and request.user.is_authenticated else None,
                        AUDIT_ACTIONS["UPDATE"],
                        module=AUDIT_MODULES["USERS"],
                        description=f"Auto-deactivated user {old_user.email} ({old_user.userlevel}) due to new user creation",
                        request=request if request else None
                    )
                except Exception as e:
                    logger.error(f"Failed to log deactivation activity: {e}")
        
        elif userlevel == "Section Chief" and section:
            old_users = User.objects.filter(userlevel="Section Chief", section=section, is_active=True)
            for old_user in old_users:
                old_user.is_active = False
                old_user.save()
                try:
                    from audit.utils import log_activity
                    from audit.constants import AUDIT_ACTIONS, AUDIT_MODULES
                    log_activity(
                        request.user if request and request.user.is_authenticated else None,
                        AUDIT_ACTIONS["UPDATE"],
                        module=AUDIT_MODULES["USERS"],
                        description=f"Auto-deactivated user {old_user.email} ({old_user.userlevel}) due to new user creation",
                        request=request if request else None
                    )
                except Exception as e:
                    logger.error(f"Failed to log deactivation activity: {e}")
        
        elif userlevel == "Unit Head" and section:
            old_users = User.objects.filter(userlevel="Unit Head", section=section, is_active=True)
            for old_user in old_users:
                old_user.is_active = False
                old_user.save()
                try:
                    from audit.utils import log_activity
                    from audit.constants import AUDIT_ACTIONS, AUDIT_MODULES
                    log_activity(
                        request.user if request and request.user.is_authenticated else None,
                        AUDIT_ACTIONS["UPDATE"],
                        module=AUDIT_MODULES["USERS"],
                        description=f"Auto-deactivated user {old_user.email} ({old_user.userlevel}) due to new user creation",
                        request=request if request else None
                    )
                except Exception as e:
                    logger.error(f"Failed to log deactivation activity: {e}")
        
        # Create user with generated password
        user = User.objects.create_user(
            password=generated_password,
            password_provided=True,  # We're providing the password, so don't trigger signal in UserManager
            **validated_data
        )
        
        # Handle avatar upload and optimization
        if avatar:
            try:
                optimized_avatar = optimize_avatar(avatar, user.id)
                user.avatar = optimized_avatar
                user.save(update_fields=['avatar'])
            except Exception as e:
                logger.error(f"Failed to optimize avatar for user {user.id}: {str(e)}")
                # Save original if optimization fails (fallback)
                user.avatar = avatar
                user.save(update_fields=['avatar'])
        
        # Send the custom signal with the generated password - THIS IS THE KEY FIX
        # This ensures ALL users get welcome emails, not just Division Chief
        user_created_with_password.send(
            sender=self.__class__,
            user=user,
            password=generated_password
        )
        
        return user


class UserSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()
    allowed_reports = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = (
            'id',
            'email',
            'first_name',
            'middle_name',
            'last_name',
            'userlevel',
            'section',
            'avatar',
            'avatar_url',  # Full URL for avatar
            'date_joined',
            'last_login',
            'updated_at',  # NEW: Include updated_at field
            'is_active',
            'must_change_password',  # Required for forced password change on first login
            'is_first_login',  # Track if user has logged in before
            'allowed_reports',  # NEW: Reports allowed for this user's role
        )
        read_only_fields = (
            'is_active',
            'must_change_password',
            'is_first_login',
            'date_joined',
            'last_login',
            'allowed_reports'
        )

    def get_avatar_url(self, obj):
        if obj.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None
    
    def get_allowed_reports(self, obj):
        """Get list of report types this user can access based on their role"""
        from reports.models import ReportAccess
        
        try:
            allowed = ReportAccess.objects.filter(role=obj.userlevel).values(
                'report_type', 'display_name'
            )
            return list(allowed)
        except Exception:
            return []


class MyTokenObtainPairSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class AdminReportUserSerializer(serializers.ModelSerializer):
    """Serializer for Admin Report - User data"""
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = (
            'id',
            'email',
            'first_name',
            'last_name',
            'full_name',
            'userlevel',
            'section',
            'date_joined',
            'updated_at',
            'is_active',
            'last_login'
        )
    
    def get_full_name(self, obj):
        """Get full name"""
        parts = [obj.first_name, obj.last_name]
        return ' '.join(filter(None, parts)) or obj.email

