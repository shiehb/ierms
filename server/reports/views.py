from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.utils import timezone


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_report_access(request):
    """
    Get list of allowed report types for the current user based on their role
    """
    from .models import ReportAccess
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        user = request.user
        user_role = user.userlevel
        
        # Log user information
        logger.info(f"[REPORT ACCESS] User: {user.email} (ID: {user.id})")
        logger.info(f"[REPORT ACCESS] User Role: '{user_role}' (type: {type(user_role).__name__})")
        
        # Check if ReportAccess table has any data
        total_access_count = ReportAccess.objects.count()
        logger.info(f"[REPORT ACCESS] Total entries in ReportAccess table: {total_access_count}")
        
        if total_access_count == 0:
            logger.error("[REPORT ACCESS] ❌ ReportAccess table is EMPTY! Need to run seed_report_access command or SQL")
            return Response({
                'role': user_role,
                'allowed_reports': [],
                'debug_info': {
                    'error': 'ReportAccess table is empty',
                    'solution': 'Run: python manage.py seed_report_access OR execute seed_report_access.sql'
                }
            }, status=status.HTTP_200_OK)
        
        # Check what roles exist in the table
        existing_roles = list(ReportAccess.objects.values_list('role', flat=True).distinct())
        logger.info(f"[REPORT ACCESS] Roles found in ReportAccess table: {existing_roles}")
        
        # Query ReportAccess table for this user's role
        allowed_reports = ReportAccess.objects.filter(role=user_role).values(
            'report_type', 'display_name'
        ).order_by('display_name')
        
        report_count = allowed_reports.count()
        logger.info(f"[REPORT ACCESS] Found {report_count} reports for role '{user_role}'")
        
        if report_count == 0:
            logger.warning(f"[REPORT ACCESS] ⚠️ No reports found for role '{user_role}'")
            logger.warning(f"[REPORT ACCESS] User role might not match database. Check spelling and case sensitivity.")
            logger.warning(f"[REPORT ACCESS] Expected one of: {existing_roles}")
            
            return Response({
                'role': user_role,
                'allowed_reports': [],
                'debug_info': {
                    'error': f'No reports configured for role: {user_role}',
                    'user_role': user_role,
                    'available_roles': existing_roles,
                    'suggestion': 'Check if user role matches exactly with database entries (case-sensitive)'
                }
            }, status=status.HTTP_200_OK)
        
        # Log each report found
        for report in allowed_reports:
            logger.info(f"[REPORT ACCESS]   ✓ {report['display_name']} ({report['report_type']})")
        
        logger.info(f"[REPORT ACCESS] ✅ Successfully returned {report_count} reports for {user.email}")
        
        return Response({
            'role': user_role,
            'allowed_reports': list(allowed_reports)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        import traceback
        logger.error(f"[REPORT ACCESS] ❌ Exception occurred: {str(e)}")
        logger.error(f"[REPORT ACCESS] Traceback: {traceback.format_exc()}")
        
        return Response({
            'error': str(e),
            'detail': 'Failed to retrieve report access',
            'debug_info': {
                'exception_type': type(e).__name__,
                'exception_message': str(e)
            }
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def generate_report(request):
    """
    Generate a report based on report type and filters
    
    Request Body:
    {
        "report_type": "inspection",
        "time_filter": "quarterly",
        "quarter": 1,
        "year": 2025,
        "date_from": "2025-01-01",  // optional, for custom range
        "date_to": "2025-03-31",    // optional, for custom range
        "extra_filters": {
            "inspector_id": 12,
            "law": "PD-1586"
        }
    }
    """
    from .models import ReportAccess
    from .generators import get_generator
    from .utils import get_quarter_dates
    
    try:
        # Validate request data
        report_type = request.data.get('report_type')
        if not report_type:
            return Response({
                'error': 'report_type is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if user has access to this report type
        import logging
        logger = logging.getLogger(__name__)
        
        user = request.user
        user_role = user.userlevel
        
        logger.info(f"[GENERATE REPORT] User: {user.email} attempting to generate '{report_type}' report")
        logger.info(f"[GENERATE REPORT] User Role: '{user_role}'")
        
        has_access = ReportAccess.objects.filter(
            role=user_role, 
            report_type=report_type
        ).exists()
        
        if not has_access:
            # Log why access was denied
            user_reports = list(ReportAccess.objects.filter(role=user_role).values_list('report_type', flat=True))
            logger.warning(f"[GENERATE REPORT] ❌ Access DENIED for {user.email}")
            logger.warning(f"[GENERATE REPORT] Requested: '{report_type}' | User's allowed reports: {user_reports}")
            
            return Response({
                'error': 'You do not have permission to access this report type',
                'detail': f'Report type "{report_type}" not allowed for role "{user_role}"',
                'debug_info': {
                    'requested_report': report_type,
                    'user_role': user_role,
                    'allowed_reports': user_reports
                }
            }, status=status.HTTP_403_FORBIDDEN)
        
        logger.info(f"[GENERATE REPORT] ✅ Access granted for {user.email} to generate '{report_type}'")
        
        # Parse time filters
        time_filter = request.data.get('time_filter', 'custom')
        date_from = request.data.get('date_from')
        date_to = request.data.get('date_to')
        
        # Handle quarterly filter
        if time_filter == 'quarterly':
            quarter = request.data.get('quarter')
            year = request.data.get('year')

            # Default to current quarter/year when missing
            if not quarter or not year:
                now = timezone.now()
                month_now = now.month
                if not quarter:
                    quarter = ((month_now - 1) // 3) + 1
                if not year:
                    year = now.year

            # Calculate date range from quarter
            try:
                quarter_dates = get_quarter_dates(int(quarter), int(year))
                date_from = quarter_dates['start']
                date_to = quarter_dates['end']
            except (ValueError, KeyError) as e:
                return Response({
                    'error': f'Invalid quarter or year: {str(e)}'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Handle monthly filter
        elif time_filter == 'monthly':
            month = request.data.get('month')
            year = request.data.get('year')

            # Default to current month/year when missing
            if not month or not year:
                now = timezone.now()
                if not month:
                    month = now.month
                if not year:
                    year = now.year

            # Calculate date range from month
            from datetime import date
            from calendar import monthrange

            try:
                month_int = int(month)
                year_int = int(year)
                date_from = date(year_int, month_int, 1)
                last_day = monthrange(year_int, month_int)[1]
                date_to = date(year_int, month_int, last_day)
            except (ValueError, TypeError) as e:
                return Response({
                    'error': f'Invalid month or year: {str(e)}'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate date range for custom filter
        elif time_filter == 'custom':
            if not date_from or not date_to:
                return Response({
                    'error': 'date_from and date_to are required for custom date range'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get extra filters
        extra_filters = request.data.get('extra_filters', {})
        
        # Prepare filters dict
        filters = {
            'time_filter': time_filter,
            'date_from': date_from,
            'date_to': date_to,
            'quarter': quarter if 'quarter' in locals() else request.data.get('quarter'),
            'year': year if 'year' in locals() else request.data.get('year'),
            'month': month if 'month' in locals() else request.data.get('month'),
            'extra_filters': extra_filters
        }
        
        # Get the appropriate report generator
        try:
            generator = get_generator(report_type)
        except ValueError as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Generate the report
        try:
            report_data = generator.generate(filters, request.user)
            return Response(report_data, status=status.HTTP_200_OK)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({
                'error': 'Failed to generate report',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({
            'error': 'An unexpected error occurred',
            'detail': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_filter_options(request):
    """
    Get available filter options for a specific report type
    
    Query Parameters:
    - report_type: The type of report to get filter options for
    """
    from establishments.models import Establishment
    from laws.models import Law
    
    try:
        report_type = request.query_params.get('report_type')
        
        if not report_type:
            return Response({
                'error': 'report_type query parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        filter_options = {}
        
        # Common filters
        years = list(range(2020, timezone.now().year + 2))
        filter_options['years'] = years
        filter_options['quarters'] = [
            {'value': 1, 'label': 'First Quarter (Jan-Mar)'},
            {'value': 2, 'label': 'Second Quarter (Apr-Jun)'},
            {'value': 3, 'label': 'Third Quarter (Jul-Sep)'},
            {'value': 4, 'label': 'Fourth Quarter (Oct-Dec)'}
        ]
        filter_options['months'] = [
            {'value': 1, 'label': 'January'},
            {'value': 2, 'label': 'February'},
            {'value': 3, 'label': 'March'},
            {'value': 4, 'label': 'April'},
            {'value': 5, 'label': 'May'},
            {'value': 6, 'label': 'June'},
            {'value': 7, 'label': 'July'},
            {'value': 8, 'label': 'August'},
            {'value': 9, 'label': 'September'},
            {'value': 10, 'label': 'October'},
            {'value': 11, 'label': 'November'},
            {'value': 12, 'label': 'December'}
        ]
        
        # Report-specific filters
        if report_type == 'establishment':
            # Get unique provinces, cities, barangays
            provinces = Establishment.objects.values_list('province', flat=True).distinct().order_by('province')
            filter_options['provinces'] = [{'value': p, 'label': p} for p in provinces if p]
            filter_options['status_options'] = [
                {'value': 'active', 'label': 'Active'},
                {'value': 'inactive', 'label': 'Inactive'},
                {'value': 'ALL', 'label': 'All'}
            ]
        
        elif report_type == 'user':
            # Get user roles
            from django.contrib.auth import get_user_model
            User = get_user_model()
            roles = User.USERLEVEL_CHOICES
            filter_options['roles'] = [{'value': r[0], 'label': r[1]} for r in roles]
            
            # Get sections
            sections = User.SECTION_CHOICES
            filter_options['sections'] = [{'value': s[0], 'label': s[1]} for s in sections]
            
            filter_options['status_options'] = [
                {'value': 'active', 'label': 'Active'},
                {'value': 'inactive', 'label': 'Inactive'},
                {'value': 'ALL', 'label': 'All'}
            ]
        
        elif report_type == 'law':
            # Get law categories
            categories = Law.objects.values_list('category', flat=True).distinct()
            filter_options['categories'] = [{'value': c, 'label': c} for c in categories if c]
            filter_options['status_options'] = [
                {'value': 'Active', 'label': 'Active'},
                {'value': 'Inactive', 'label': 'Inactive'},
                {'value': 'ALL', 'label': 'All'}
            ]
        
        elif report_type in ['inspection', 'compliance', 'non_compliant', 'section_accomplishment', 'unit_accomplishment', 'monitoring_accomplishment']:
            # Get available laws
            laws = Law.objects.filter(status='Active').values('reference_code', 'law_title')
            filter_options['laws'] = [
                {'value': law['reference_code'], 'label': f"{law['reference_code']} - {law['law_title']}"} 
                for law in laws
            ]
            
            # Compliance filter for accomplishment reports
            if report_type in ['section_accomplishment', 'unit_accomplishment', 'monitoring_accomplishment']:
                filter_options['compliance_options'] = [
                    {'value': 'ALL', 'label': 'All'},
                    {'value': 'compliant', 'label': 'Compliant'},
                    {'value': 'non_compliant', 'label': 'Non-Compliant'},
                ]
            
            # Get inspectors (users who can be assigned) - only for inspection report
            if report_type == 'inspection':
                from django.contrib.auth import get_user_model
                User = get_user_model()
                inspectors = User.objects.filter(
                    is_active=True
                ).exclude(userlevel='Admin').values('id', 'first_name', 'last_name', 'email')
                filter_options['inspectors'] = [
                    {
                        'value': insp['id'], 
                        'label': f"{insp['first_name']} {insp['last_name']}" if insp['first_name'] else insp['email']
                    } 
                    for insp in inspectors
                ]
        
        elif report_type == 'billing':
            filter_options['status_options'] = [
                {'value': 'UNPAID', 'label': 'Unpaid'},
                {'value': 'PAID', 'label': 'Paid'},
                {'value': 'ALL', 'label': 'All'}
            ]
        
        elif report_type == 'quota':
            # Get available laws from quota records
            from inspections.models import ComplianceQuota
            laws = ComplianceQuota.objects.values_list('law', flat=True).distinct()
            filter_options['laws'] = [{'value': law, 'label': law} for law in laws if law]
        
        elif report_type in ['nov', 'noo']:
            # Get available laws
            laws = Law.objects.filter(status='Active').values('reference_code', 'law_title')
            filter_options['laws'] = [
                {'value': law['reference_code'], 'label': f"{law['reference_code']} - {law['law_title']}"} 
                for law in laws
            ]
            
            # Get establishments
            establishments = Establishment.objects.filter(is_active=True).values('id', 'name')
            filter_options['establishments'] = [
                {'value': est['id'], 'label': est['name']} 
                for est in establishments
            ]
            
            # Get users who can send NOV/NOO
            from django.contrib.auth import get_user_model
            User = get_user_model()
            senders = User.objects.filter(is_active=True).values('id', 'first_name', 'last_name', 'email')
            filter_options['senders'] = [
                {
                    'value': sender['id'], 
                    'label': f"{sender['first_name']} {sender['last_name']}" if sender['first_name'] else sender['email']
                } 
                for sender in senders
            ]
            
            # Status options
            filter_options['status_options'] = [
                {'value': 'ALL', 'label': 'All'},
                {'value': 'PENDING', 'label': 'Pending'},
                {'value': 'OVERDUE', 'label': 'Overdue'},
            ]
        
        return Response(filter_options, status=status.HTTP_200_OK)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({
            'error': 'Failed to retrieve filter options',
            'detail': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
