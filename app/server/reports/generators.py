"""
Report Generator Functions
Handles generation of different report types with consistent structure
"""
from datetime import datetime, date
from decimal import Decimal
from django.db.models import Q, Count, Avg
from django.contrib.auth import get_user_model
from establishments.models import Establishment
from inspections.models import Inspection, BillingRecord, ComplianceQuota, NoticeOfViolation, NoticeOfOrder
from laws.models import Law

User = get_user_model()


class BaseReportGenerator:
    """
    Base class for all report generators
    Ensures consistent structure across all reports
    """
    report_type = None
    report_title = None
    
    def generate(self, filters, user):
        """
        Main entry point for report generation
        
        Args:
            filters: dict with date_from, date_to, and report-specific filters
            user: current user making the request
        
        Returns:
            dict with columns, rows, and metadata
        """
        # Apply date filtering
        date_from = filters.get('date_from')
        date_to = filters.get('date_to')
        extra_filters = filters.get('extra_filters', {})
        
        # Fetch data with filters
        data = self.fetch_data(date_from, date_to, extra_filters, user)
        
        # Format the data
        return {
            'columns': self.get_columns(),
            'rows': self.format_rows(data),
            'metadata': self.get_metadata(data, filters)
        }
    
    def fetch_data(self, date_from, date_to, extra_filters, user):
        """Fetch raw data from database - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement fetch_data()")
    
    def get_columns(self):
        """Define column structure - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement get_columns()")
    
    def format_rows(self, data):
        """Format data into table rows - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement format_rows()")
    
    def get_metadata(self, data, filters):
        """Generate report metadata"""
        return {
            'report_type': self.report_type,
            'report_title': self.report_title,
            'total': len(data) if hasattr(data, '__len__') else data.count() if hasattr(data, 'count') else 0,
            'generated_at': datetime.now().isoformat(),
            'filters_applied': {
                'date_from': filters.get('date_from'),
                'date_to': filters.get('date_to'),
                'time_filter': filters.get('time_filter'),
                'quarter': filters.get('quarter'),
                'year': filters.get('year'),
                'extra_filters': filters.get('extra_filters', {})
            }
        }
    
    def apply_date_filter(self, queryset, date_field, date_from, date_to):
        """Helper to apply date range filtering"""
        if date_from:
            queryset = queryset.filter(**{f"{date_field}__gte": date_from})
        if date_to:
            queryset = queryset.filter(**{f"{date_field}__lte": date_to})
        return queryset


class InspectionReportGenerator(BaseReportGenerator):
    """Generate inspection reports with filtering"""
    report_type = 'inspection'
    report_title = 'Inspection Report'
    
    def get_columns(self):
        return [
            {'key': 'code', 'label': 'Inspection Code'},
            {'key': 'establishment_names', 'label': 'Establishments'},
            {'key': 'law', 'label': 'Law'},
            {'key': 'district', 'label': 'District'},
            {'key': 'status', 'label': 'Status'},
            {'key': 'assigned_to', 'label': 'Assigned To'},
            {'key': 'created_by', 'label': 'Created By'},
            {'key': 'created_at', 'label': 'Created Date'},
        ]
    
    def fetch_data(self, date_from, date_to, extra_filters, user):
        """Fetch inspection data"""
        queryset = Inspection.objects.all().select_related(
            'assigned_to', 'created_by'
        ).prefetch_related('establishments')
        
        # Apply date filter
        queryset = self.apply_date_filter(queryset, 'created_at', date_from, date_to)
        
        # Apply extra filters
        inspector_id = extra_filters.get('inspector_id')
        if inspector_id:
            queryset = queryset.filter(assigned_to_id=inspector_id)
        
        inspection_type = extra_filters.get('inspection_type')
        if inspection_type:
            queryset = queryset.filter(current_status=inspection_type)
        
        establishment_id = extra_filters.get('establishment_id')
        if establishment_id:
            queryset = queryset.filter(establishments__id=establishment_id)
        
        law = extra_filters.get('law')
        if law:
            queryset = queryset.filter(law=law)
        
        district = extra_filters.get('district')
        if district and district != 'ALL':
            queryset = queryset.filter(district=district)
        
        return queryset.order_by('-created_at')
    
    def format_rows(self, data):
        """Format inspection data into table rows"""
        rows = []
        for inspection in data:
            # Get establishment names
            establishment_names = ', '.join([
                est.name for est in inspection.establishments.all()
            ])
            
            rows.append({
                'code': inspection.code or 'N/A',
                'establishment_names': establishment_names or 'N/A',
                'law': inspection.law,
                'district': inspection.district or 'N/A',
                'status': inspection.get_current_status_display(),
                'assigned_to': self._format_user(inspection.assigned_to),
                'created_by': self._format_user(inspection.created_by),
                'created_at': inspection.created_at.strftime('%Y-%m-%d %H:%M') if inspection.created_at else 'N/A',
            })
        return rows
    
    def _format_user(self, user):
        """Format user display name"""
        if not user:
            return 'N/A'
        if user.first_name and user.last_name:
            return f"{user.first_name} {user.last_name}"
        return user.email


class EstablishmentReportGenerator(BaseReportGenerator):
    """Generate establishment reports with filtering"""
    report_type = 'establishment'
    report_title = 'Establishment Report'
    
    def get_columns(self):
        return [
            {'key': 'name', 'label': 'Establishment Name'},
            {'key': 'nature_of_business', 'label': 'Nature of Business'},
            {'key': 'province', 'label': 'Province'},
            {'key': 'city', 'label': 'City'},
            {'key': 'barangay', 'label': 'Barangay'},
            {'key': 'street_building', 'label': 'Street/Building'},
            {'key': 'year_established', 'label': 'Year Established'},
            {'key': 'status', 'label': 'Status'},
            {'key': 'inspection_count', 'label': 'Total Inspections'},
            {'key': 'created_at', 'label': 'Date Added'},
        ]
    
    def fetch_data(self, date_from, date_to, extra_filters, user):
        """Fetch establishment data"""
        queryset = Establishment.objects.all().annotate(
            inspection_count=Count('inspections_new')
        )
        
        # Apply date filter on created_at
        queryset = self.apply_date_filter(queryset, 'created_at', date_from, date_to)
        
        # Apply extra filters
        province = extra_filters.get('province')
        if province and province != 'ALL':
            queryset = queryset.filter(province__iexact=province)
        
        city = extra_filters.get('city')
        if city and city != 'ALL':
            queryset = queryset.filter(city__iexact=city)
        
        barangay = extra_filters.get('barangay')
        if barangay and barangay != 'ALL':
            queryset = queryset.filter(barangay__iexact=barangay)
        
        status = extra_filters.get('status')
        if status and status != 'ALL':
            if status == 'active':
                queryset = queryset.filter(is_active=True)
            elif status == 'inactive':
                queryset = queryset.filter(is_active=False)
        
        return queryset.order_by('-created_at')
    
    def format_rows(self, data):
        """Format establishment data into table rows"""
        rows = []
        for establishment in data:
            rows.append({
                'name': establishment.name,
                'nature_of_business': establishment.nature_of_business,
                'province': establishment.province,
                'city': establishment.city,
                'barangay': establishment.barangay,
                'street_building': establishment.street_building,
                'year_established': establishment.year_established,
                'status': 'Active' if establishment.is_active else 'Inactive',
                'inspection_count': establishment.inspection_count,
                'created_at': establishment.created_at.strftime('%Y-%m-%d') if establishment.created_at else 'N/A',
            })
        return rows


class UserReportGenerator(BaseReportGenerator):
    """Generate user reports with filtering"""
    report_type = 'user'
    report_title = 'User Report'
    
    def get_columns(self):
        return [
            {'key': 'email', 'label': 'Email'},
            {'key': 'full_name', 'label': 'Full Name'},
            {'key': 'userlevel', 'label': 'Role'},
            {'key': 'section', 'label': 'Section'},
            {'key': 'status', 'label': 'Status'},
            {'key': 'date_joined', 'label': 'Date Joined'},
            {'key': 'last_login', 'label': 'Last Login'},
            {'key': 'inspections_created', 'label': 'Inspections Created'},
            {'key': 'inspections_assigned', 'label': 'Inspections Assigned'},
        ]
    
    def fetch_data(self, date_from, date_to, extra_filters, user):
        """Fetch user data"""
        queryset = User.objects.exclude(userlevel='Admin').annotate(
            inspections_created=Count('inspections_created_new'),
            inspections_assigned=Count('inspections_assigned_new')
        )
        
        # Apply date filter on date_joined
        queryset = self.apply_date_filter(queryset, 'date_joined', date_from, date_to)
        
        # Apply extra filters
        role = extra_filters.get('role')
        if role and role != 'ALL':
            queryset = queryset.filter(userlevel=role)
        
        section = extra_filters.get('section')
        if section and section != 'ALL':
            queryset = queryset.filter(section=section)
        
        status = extra_filters.get('status')
        if status and status != 'ALL':
            if status == 'active':
                queryset = queryset.filter(is_active=True)
            elif status == 'inactive':
                queryset = queryset.filter(is_active=False)
        
        return queryset.order_by('-date_joined')
    
    def format_rows(self, data):
        """Format user data into table rows"""
        rows = []
        for user in data:
            full_name = f"{user.first_name} {user.last_name}".strip() or 'N/A'
            
            rows.append({
                'email': user.email,
                'full_name': full_name,
                'userlevel': user.userlevel,
                'section': user.section or 'N/A',
                'status': 'Active' if user.is_active else 'Inactive',
                'date_joined': user.date_joined.strftime('%Y-%m-%d') if user.date_joined else 'N/A',
                'last_login': user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else 'Never',
                'inspections_created': user.inspections_created,
                'inspections_assigned': user.inspections_assigned,
            })
        return rows


class BillingReportGenerator(BaseReportGenerator):
    """Generate billing reports with filtering"""
    report_type = 'billing'
    report_title = 'Billing Report'
    
    def get_columns(self):
        return [
            {'key': 'billing_code', 'label': 'Billing Code'},
            {'key': 'establishment_name', 'label': 'Establishment'},
            {'key': 'related_law', 'label': 'Law'},
            {'key': 'billing_type', 'label': 'Type'},
            {'key': 'amount', 'label': 'Amount'},
            {'key': 'payment_status', 'label': 'Status'},
            {'key': 'due_date', 'label': 'Due Date'},
            {'key': 'payment_date', 'label': 'Payment Date'},
            {'key': 'created_at', 'label': 'Created Date'},
        ]
    
    def fetch_data(self, date_from, date_to, extra_filters, user):
        """Fetch billing data"""
        queryset = BillingRecord.objects.all().select_related('establishment', 'inspection')
        
        # Apply date filter
        queryset = self.apply_date_filter(queryset, 'created_at', date_from, date_to)
        
        # Apply extra filters
        payment_status = extra_filters.get('status')
        if payment_status and payment_status != 'ALL':
            queryset = queryset.filter(payment_status=payment_status.upper())
        
        billing_code = extra_filters.get('billing_code')
        if billing_code:
            queryset = queryset.filter(billing_code__icontains=billing_code)
        
        min_amount = extra_filters.get('min_amount')
        if min_amount:
            queryset = queryset.filter(amount__gte=Decimal(min_amount))
        
        max_amount = extra_filters.get('max_amount')
        if max_amount:
            queryset = queryset.filter(amount__lte=Decimal(max_amount))
        
        return queryset.order_by('-created_at')
    
    def format_rows(self, data):
        """Format billing data into table rows"""
        rows = []
        for billing in data:
            rows.append({
                'billing_code': billing.billing_code,
                'establishment_name': billing.establishment_name,
                'related_law': billing.related_law,
                'billing_type': billing.get_billing_type_display(),
                'amount': f"₱{billing.amount:,.2f}",
                'payment_status': billing.get_payment_status_display(),
                'due_date': billing.due_date.strftime('%Y-%m-%d') if billing.due_date else 'N/A',
                'payment_date': billing.payment_date.strftime('%Y-%m-%d') if billing.payment_date else 'N/A',
                'created_at': billing.created_at.strftime('%Y-%m-%d') if billing.created_at else 'N/A',
            })
        return rows


class ComplianceReportGenerator(BaseReportGenerator):
    """Generate compliance reports (compliant inspections)"""
    report_type = 'compliance'
    report_title = 'Compliance Report'
    
    def get_columns(self):
        return [
            {'key': 'code', 'label': 'Inspection Code'},
            {'key': 'establishment_names', 'label': 'Establishments'},
            {'key': 'law', 'label': 'Law'},
            {'key': 'status', 'label': 'Status'},
            {'key': 'assigned_to', 'label': 'Inspector'},
            {'key': 'created_at', 'label': 'Inspection Date'},
        ]
    
    def fetch_data(self, date_from, date_to, extra_filters, user):
        """Fetch compliant inspections"""
        # Filter for compliant statuses
        compliant_statuses = [
            'SECTION_COMPLETED_COMPLIANT',
            'UNIT_COMPLETED_COMPLIANT',
            'MONITORING_COMPLETED_COMPLIANT',
            'CLOSED_COMPLIANT'
        ]
        
        queryset = Inspection.objects.filter(
            current_status__in=compliant_statuses
        ).select_related('assigned_to', 'created_by').prefetch_related('establishments')
        
        # Apply date filter
        queryset = self.apply_date_filter(queryset, 'created_at', date_from, date_to)
        
        # Apply extra filters
        law = extra_filters.get('law')
        if law and law != 'ALL':
            queryset = queryset.filter(law=law)
        
        return queryset.order_by('-created_at')
    
    def format_rows(self, data):
        """Format compliance data into table rows"""
        rows = []
        for inspection in data:
            establishment_names = ', '.join([
                est.name for est in inspection.establishments.all()
            ])
            
            assigned_to = 'N/A'
            if inspection.assigned_to:
                if inspection.assigned_to.first_name and inspection.assigned_to.last_name:
                    assigned_to = f"{inspection.assigned_to.first_name} {inspection.assigned_to.last_name}"
                else:
                    assigned_to = inspection.assigned_to.email
            
            rows.append({
                'code': inspection.code or 'N/A',
                'establishment_names': establishment_names or 'N/A',
                'law': inspection.law,
                'status': inspection.get_current_status_display(),
                'assigned_to': assigned_to,
                'created_at': inspection.created_at.strftime('%Y-%m-%d') if inspection.created_at else 'N/A',
            })
        return rows


class NonCompliantReportGenerator(BaseReportGenerator):
    """Generate non-compliant reports"""
    report_type = 'non_compliant'
    report_title = 'Non-Compliant Report'
    
    def get_columns(self):
        return [
            {'key': 'code', 'label': 'Inspection Code'},
            {'key': 'establishment_names', 'label': 'Establishments'},
            {'key': 'law', 'label': 'Law'},
            {'key': 'status', 'label': 'Status'},
            {'key': 'assigned_to', 'label': 'Inspector'},
            {'key': 'has_billing', 'label': 'Billing Status'},
            {'key': 'created_at', 'label': 'Inspection Date'},
        ]
    
    def fetch_data(self, date_from, date_to, extra_filters, user):
        """Fetch non-compliant inspections"""
        # Filter for non-compliant statuses
        non_compliant_statuses = [
            'SECTION_COMPLETED_NON_COMPLIANT',
            'UNIT_COMPLETED_NON_COMPLIANT',
            'MONITORING_COMPLETED_NON_COMPLIANT',
            'LEGAL_REVIEW',
            'NOV_SENT',
            'NOO_SENT',
            'CLOSED_NON_COMPLIANT'
        ]
        
        queryset = Inspection.objects.filter(
            current_status__in=non_compliant_statuses
        ).select_related('assigned_to', 'created_by').prefetch_related('establishments')
        
        # Apply date filter
        queryset = self.apply_date_filter(queryset, 'created_at', date_from, date_to)
        
        # Apply extra filters
        law = extra_filters.get('law')
        if law and law != 'ALL':
            queryset = queryset.filter(law=law)
        
        has_billing = extra_filters.get('has_billing')
        if has_billing == 'yes':
            queryset = queryset.filter(billing_record__isnull=False)
        elif has_billing == 'no':
            queryset = queryset.filter(billing_record__isnull=True)
        
        return queryset.order_by('-created_at')
    
    def format_rows(self, data):
        """Format non-compliant data into table rows"""
        rows = []
        for inspection in data:
            establishment_names = ', '.join([
                est.name for est in inspection.establishments.all()
            ])
            
            assigned_to = 'N/A'
            if inspection.assigned_to:
                if inspection.assigned_to.first_name and inspection.assigned_to.last_name:
                    assigned_to = f"{inspection.assigned_to.first_name} {inspection.assigned_to.last_name}"
                else:
                    assigned_to = inspection.assigned_to.email
            
            # Check if billing exists
            has_billing = 'Billed' if hasattr(inspection, 'billing_record') else 'Not Billed'
            
            rows.append({
                'code': inspection.code or 'N/A',
                'establishment_names': establishment_names or 'N/A',
                'law': inspection.law,
                'status': inspection.get_current_status_display(),
                'assigned_to': assigned_to,
                'has_billing': has_billing,
                'created_at': inspection.created_at.strftime('%Y-%m-%d') if inspection.created_at else 'N/A',
            })
        return rows


class QuotaReportGenerator(BaseReportGenerator):
    """Generate quota reports"""
    report_type = 'quota'
    report_title = 'Quota Report'
    
    def get_columns(self):
        return [
            {'key': 'law', 'label': 'Law'},
            {'key': 'year', 'label': 'Year'},
            {'key': 'month', 'label': 'Month'},
            {'key': 'quarter', 'label': 'Quarter'},
            {'key': 'target', 'label': 'Target'},
            {'key': 'auto_adjusted', 'label': 'Auto Adjusted'},
            {'key': 'created_by', 'label': 'Created By'},
            {'key': 'created_at', 'label': 'Created Date'},
        ]
    
    def fetch_data(self, date_from, date_to, extra_filters, user):
        """Fetch quota data"""
        queryset = ComplianceQuota.objects.all().select_related('created_by')
        
        # Apply year/quarter filters
        year = extra_filters.get('year')
        if year:
            queryset = queryset.filter(year=year)
        
        quarter = extra_filters.get('quarter')
        if quarter:
            queryset = queryset.filter(quarter=quarter)
        
        law = extra_filters.get('law')
        if law and law != 'ALL':
            queryset = queryset.filter(law=law)
        
        return queryset.order_by('-year', '-month')
    
    def format_rows(self, data):
        """Format quota data into table rows"""
        month_names = {
            1: 'January', 2: 'February', 3: 'March', 4: 'April',
            5: 'May', 6: 'June', 7: 'July', 8: 'August',
            9: 'September', 10: 'October', 11: 'November', 12: 'December'
        }
        
        rows = []
        for quota in data:
            created_by = 'System'
            if quota.created_by:
                if quota.created_by.first_name and quota.created_by.last_name:
                    created_by = f"{quota.created_by.first_name} {quota.created_by.last_name}"
                else:
                    created_by = quota.created_by.email
            
            rows.append({
                'law': quota.law,
                'year': quota.year,
                'month': month_names.get(quota.month, str(quota.month)),
                'quarter': f"Q{quota.quarter}",
                'target': quota.target,
                'auto_adjusted': 'Yes' if quota.auto_adjusted else 'No',
                'created_by': created_by,
                'created_at': quota.created_at.strftime('%Y-%m-%d') if quota.created_at else 'N/A',
            })
        return rows


class LawReportGenerator(BaseReportGenerator):
    """Generate law reports"""
    report_type = 'law'
    report_title = 'Law Report'
    
    def get_columns(self):
        return [
            {'key': 'reference_code', 'label': 'Reference Code'},
            {'key': 'title', 'label': 'Title'},
            {'key': 'category', 'label': 'Category'},
            {'key': 'description', 'label': 'Description'},
            {'key': 'effective_date', 'label': 'Effective Date'},
            {'key': 'status', 'label': 'Status'},
            {'key': 'created_at', 'label': 'Date Added'},
        ]
    
    def fetch_data(self, date_from, date_to, extra_filters, user):
        """Fetch law data"""
        # Note: Law model doesn't have direct FK relationship with Inspection
        # Inspection.law is a CharField, not a ForeignKey
        queryset = Law.objects.all()
        
        # Apply date filter
        queryset = self.apply_date_filter(queryset, 'created_at', date_from, date_to)
        
        # Apply extra filters
        category = extra_filters.get('category')
        if category and category != 'ALL':
            queryset = queryset.filter(category__iexact=category)
        
        status = extra_filters.get('status')
        if status and status != 'ALL':
            if status == 'Active':
                queryset = queryset.filter(status='Active')
            elif status == 'Inactive':
                queryset = queryset.filter(status='Inactive')
        
        return queryset.order_by('reference_code')
    
    def format_rows(self, data):
        """Format law data into table rows"""
        rows = []
        for law in data:
            rows.append({
                'reference_code': law.reference_code or 'N/A',
                'title': law.law_title,
                'category': law.category or 'N/A',
                'description': law.description[:100] + '...' if len(law.description) > 100 else law.description,
                'effective_date': law.effective_date.strftime('%Y-%m-%d') if law.effective_date else 'N/A',
                'status': law.status,
                'created_at': law.created_at.strftime('%Y-%m-%d') if law.created_at else 'N/A',
            })
        return rows


class SectionAccomplishmentReportGenerator(BaseReportGenerator):
    """Generate accomplishment reports for Section Chief"""
    report_type = 'section_accomplishment'
    report_title = 'Section Accomplishment Report'
    
    def get_columns(self):
        return [
            {'key': 'code', 'label': 'Inspection Code'},
            {'key': 'establishment_names', 'label': 'Establishments'},
            {'key': 'law', 'label': 'Law'},
            {'key': 'status', 'label': 'Status'},
            {'key': 'compliance_decision', 'label': 'Compliance'},
            {'key': 'assigned_to', 'label': 'Assigned To'},
            {'key': 'completed_at', 'label': 'Completed Date'},
        ]
    
    def fetch_data(self, date_from, date_to, extra_filters, user):
        """Fetch completed inspections for section"""
        # Get completed statuses for section level
        completed_statuses = [
            'SECTION_COMPLETED_COMPLIANT',
            'SECTION_COMPLETED_NON_COMPLIANT',
            'SECTION_REVIEWED',
            'UNIT_REVIEWED',
            'DIVISION_REVIEWED',
            'CLOSED_COMPLIANT',
            'CLOSED_NON_COMPLIANT',
        ]
        
        queryset = Inspection.objects.filter(
            current_status__in=completed_statuses
        ).select_related('assigned_to', 'created_by').prefetch_related('establishments')
        
        # Apply date filter
        queryset = self.apply_date_filter(queryset, 'updated_at', date_from, date_to)
        
        # Apply compliance filter
        compliance = extra_filters.get('compliance')
        if compliance and compliance != 'ALL':
            if compliance == 'compliant':
                queryset = queryset.filter(current_status__contains='COMPLIANT')
            elif compliance == 'non_compliant':
                queryset = queryset.filter(current_status__contains='NON_COMPLIANT')
        
        # Apply law filter (if provided)
        law = extra_filters.get('law')
        if law and law != 'ALL':
            queryset = queryset.filter(law=law)
        
        # ENFORCE user-based filtering LAST (cannot be overridden)
        if user.userlevel == 'Section Chief' and user.section:
            # Handle combined sections
            if user.section == 'PD-1586,RA-8749,RA-9275':
                queryset = queryset.filter(law__in=['PD-1586', 'RA-8749', 'RA-9275'])
            else:
                queryset = queryset.filter(law=user.section)
        elif user.userlevel not in ['Admin', 'Division Chief']:
            # Only Section Chief, Division Chief, and Admin can access this report
            queryset = queryset.none()
        
        return queryset.order_by('-updated_at')
    
    def format_rows(self, data):
        """Format section accomplishment data"""
        rows = []
        for inspection in data:
            establishment_names = ', '.join([
                est.name for est in inspection.establishments.all()
            ])
            
            # Determine compliance
            if 'COMPLIANT' in inspection.current_status and 'NON' not in inspection.current_status:
                compliance = 'Compliant'
            elif 'NON_COMPLIANT' in inspection.current_status:
                compliance = 'Non-Compliant'
            else:
                compliance = 'Pending'
            
            rows.append({
                'code': inspection.code or 'N/A',
                'establishment_names': establishment_names or 'N/A',
                'law': inspection.law,
                'status': inspection.get_current_status_display(),
                'compliance_decision': compliance,
                'assigned_to': self._format_user(inspection.assigned_to),
                'completed_at': inspection.updated_at.strftime('%Y-%m-%d') if inspection.updated_at else 'N/A',
            })
        return rows
    
    def _format_user(self, user):
        if not user:
            return 'N/A'
        if user.first_name and user.last_name:
            return f"{user.first_name} {user.last_name}"
        return user.email


class UnitAccomplishmentReportGenerator(BaseReportGenerator):
    """Generate accomplishment reports for Unit Head"""
    report_type = 'unit_accomplishment'
    report_title = 'Unit Accomplishment Report'
    
    def get_columns(self):
        return [
            {'key': 'code', 'label': 'Inspection Code'},
            {'key': 'establishment_names', 'label': 'Establishments'},
            {'key': 'law', 'label': 'Law'},
            {'key': 'status', 'label': 'Status'},
            {'key': 'compliance_decision', 'label': 'Compliance'},
            {'key': 'assigned_to', 'label': 'Assigned To'},
            {'key': 'completed_at', 'label': 'Completed Date'},
        ]
    
    def fetch_data(self, date_from, date_to, extra_filters, user):
        """Fetch completed inspections for unit"""
        # Get completed statuses for unit level
        completed_statuses = [
            'UNIT_COMPLETED_COMPLIANT',
            'UNIT_COMPLETED_NON_COMPLIANT',
            'UNIT_REVIEWED',
            'SECTION_REVIEWED',
            'DIVISION_REVIEWED',
            'CLOSED_COMPLIANT',
            'CLOSED_NON_COMPLIANT',
        ]
        
        queryset = Inspection.objects.filter(
            current_status__in=completed_statuses
        ).select_related('assigned_to', 'created_by').prefetch_related('establishments')
        
        # Apply date filter
        queryset = self.apply_date_filter(queryset, 'updated_at', date_from, date_to)
        
        # Apply compliance filter
        compliance = extra_filters.get('compliance')
        if compliance and compliance != 'ALL':
            if compliance == 'compliant':
                queryset = queryset.filter(current_status__contains='COMPLIANT')
            elif compliance == 'non_compliant':
                queryset = queryset.filter(current_status__contains='NON_COMPLIANT')
        
        # Apply law filter (if provided)
        law = extra_filters.get('law')
        if law and law != 'ALL':
            queryset = queryset.filter(law=law)
        
        # ENFORCE user-based filtering LAST (cannot be overridden)
        if user.userlevel == 'Unit Head' and user.section:
            # Handle combined sections
            if user.section == 'PD-1586,RA-8749,RA-9275':
                queryset = queryset.filter(law__in=['PD-1586', 'RA-8749', 'RA-9275'])
            else:
                queryset = queryset.filter(law=user.section)
        elif user.userlevel not in ['Admin', 'Division Chief']:
            # Only Unit Head, Division Chief, and Admin can access this report
            queryset = queryset.none()
        
        return queryset.order_by('-updated_at')
    
    def format_rows(self, data):
        """Format unit accomplishment data"""
        rows = []
        for inspection in data:
            establishment_names = ', '.join([
                est.name for est in inspection.establishments.all()
            ])
            
            # Determine compliance
            if 'COMPLIANT' in inspection.current_status and 'NON' not in inspection.current_status:
                compliance = 'Compliant'
            elif 'NON_COMPLIANT' in inspection.current_status:
                compliance = 'Non-Compliant'
            else:
                compliance = 'Pending'
            
            rows.append({
                'code': inspection.code or 'N/A',
                'establishment_names': establishment_names or 'N/A',
                'law': inspection.law,
                'status': inspection.get_current_status_display(),
                'compliance_decision': compliance,
                'assigned_to': self._format_user(inspection.assigned_to),
                'completed_at': inspection.updated_at.strftime('%Y-%m-%d') if inspection.updated_at else 'N/A',
            })
        return rows
    
    def _format_user(self, user):
        if not user:
            return 'N/A'
        if user.first_name and user.last_name:
            return f"{user.first_name} {user.last_name}"
        return user.email


class MonitoringAccomplishmentReportGenerator(BaseReportGenerator):
    """Generate accomplishment reports for Monitoring Personnel"""
    report_type = 'monitoring_accomplishment'
    report_title = 'Monitoring Accomplishment Report'
    
    def get_columns(self):
        return [
            {'key': 'code', 'label': 'Inspection Code'},
            {'key': 'establishment_names', 'label': 'Establishments'},
            {'key': 'law', 'label': 'Law'},
            {'key': 'status', 'label': 'Status'},
            {'key': 'compliance_decision', 'label': 'Compliance'},
            {'key': 'assigned_to', 'label': 'Assigned To'},
            {'key': 'completed_at', 'label': 'Completed Date'},
        ]
    
    def fetch_data(self, date_from, date_to, extra_filters, user):
        """Fetch completed inspections for monitoring"""
        # Get completed statuses for monitoring level
        completed_statuses = [
            'MONITORING_COMPLETED_COMPLIANT',
            'MONITORING_COMPLETED_NON_COMPLIANT',
            'UNIT_REVIEWED',
            'SECTION_REVIEWED',
            'DIVISION_REVIEWED',
            'CLOSED_COMPLIANT',
            'CLOSED_NON_COMPLIANT',
        ]
        
        queryset = Inspection.objects.filter(
            current_status__in=completed_statuses
        ).select_related('assigned_to', 'created_by').prefetch_related('establishments')
        
        # Apply date filter
        queryset = self.apply_date_filter(queryset, 'updated_at', date_from, date_to)
        
        # Apply compliance filter
        compliance = extra_filters.get('compliance')
        if compliance and compliance != 'ALL':
            if compliance == 'compliant':
                queryset = queryset.filter(current_status__contains='COMPLIANT')
            elif compliance == 'non_compliant':
                queryset = queryset.filter(current_status__contains='NON_COMPLIANT')
        
        # Apply law filter (if provided)
        law = extra_filters.get('law')
        if law and law != 'ALL':
            queryset = queryset.filter(law=law)
        
        # ENFORCE user-based filtering LAST (cannot be overridden)
        if user.userlevel == 'Monitoring Personnel':
            queryset = queryset.filter(assigned_to=user)
        elif user.userlevel not in ['Admin', 'Division Chief']:
            # Only Monitoring Personnel, Division Chief, and Admin can access this report
            queryset = queryset.none()
        
        return queryset.order_by('-updated_at')
    
    def format_rows(self, data):
        """Format monitoring accomplishment data"""
        rows = []
        for inspection in data:
            establishment_names = ', '.join([
                est.name for est in inspection.establishments.all()
            ])
            
            # Determine compliance
            if 'COMPLIANT' in inspection.current_status and 'NON' not in inspection.current_status:
                compliance = 'Compliant'
            elif 'NON_COMPLIANT' in inspection.current_status:
                compliance = 'Non-Compliant'
            else:
                compliance = 'Pending'
            
            rows.append({
                'code': inspection.code or 'N/A',
                'establishment_names': establishment_names or 'N/A',
                'law': inspection.law,
                'status': inspection.get_current_status_display(),
                'compliance_decision': compliance,
                'assigned_to': self._format_user(inspection.assigned_to),
                'completed_at': inspection.updated_at.strftime('%Y-%m-%d') if inspection.updated_at else 'N/A',
            })
        return rows
    
    def _format_user(self, user):
        if not user:
            return 'N/A'
        if user.first_name and user.last_name:
            return f"{user.first_name} {user.last_name}"
        return user.email


class NoticeOfViolationReportGenerator(BaseReportGenerator):
    """Generate Notice of Violation (NOV) reports"""
    report_type = 'nov'
    report_title = 'Notice of Violation Report'
    
    def get_columns(self):
        return [
            {'key': 'inspection_code', 'label': 'Inspection Code'},
            {'key': 'establishment_name', 'label': 'Establishment'},
            {'key': 'law', 'label': 'Law'},
            {'key': 'sent_date', 'label': 'Date Sent'},
            {'key': 'compliance_deadline', 'label': 'Compliance Deadline'},
            {'key': 'violations', 'label': 'Violations'},
            {'key': 'recipient_name', 'label': 'Recipient'},
            {'key': 'sent_by', 'label': 'Sent By'},
            {'key': 'status', 'label': 'Status'},
        ]
    
    def fetch_data(self, date_from, date_to, extra_filters, user):
        queryset = NoticeOfViolation.objects.select_related(
            'inspection_form__inspection',
            'sent_by'
        ).prefetch_related(
            'inspection_form__inspection__establishments'
        )
        
        # Apply date filter on sent_date
        queryset = self.apply_date_filter(queryset, 'sent_date', date_from, date_to)
        
        # Apply extra filters
        if 'law' in extra_filters and extra_filters['law'] != 'ALL':
            queryset = queryset.filter(inspection_form__inspection__law=extra_filters['law'])
        
        if 'establishment_id' in extra_filters and extra_filters['establishment_id']:
            queryset = queryset.filter(inspection_form__inspection__establishments__id=extra_filters['establishment_id'])
        
        if 'sent_by_id' in extra_filters and extra_filters['sent_by_id']:
            queryset = queryset.filter(sent_by__id=extra_filters['sent_by_id'])
        
        if 'status' in extra_filters and extra_filters['status'] != 'ALL':
            # Filter by compliance status
            if extra_filters['status'] == 'PENDING':
                queryset = queryset.filter(
                    compliance_deadline__gte=datetime.now().date()
                )
            elif extra_filters['status'] == 'OVERDUE':
                queryset = queryset.filter(
                    compliance_deadline__lt=datetime.now().date()
                )
        
        return queryset.order_by('-sent_date')
    
    def format_rows(self, data):
        rows = []
        for nov in data:
            inspection = nov.inspection_form.inspection
            establishment_names = ', '.join([est.name for est in inspection.establishments.all()])
            
            # Determine status
            if nov.compliance_deadline:
                if nov.compliance_deadline.date() < datetime.now().date():
                    status = 'Overdue'
                elif nov.compliance_deadline.date() == datetime.now().date():
                    status = 'Due Today'
                else:
                    status = 'Pending'
            else:
                status = 'No Deadline'
            
            rows.append({
                'inspection_code': inspection.code,
                'establishment_name': establishment_names,
                'law': inspection.law,
                'sent_date': nov.sent_date.strftime('%Y-%m-%d') if nov.sent_date else 'Not Sent',
                'compliance_deadline': nov.compliance_deadline.strftime('%Y-%m-%d %H:%M') if nov.compliance_deadline else 'N/A',
                'violations': (nov.violations[:100] + '...') if nov.violations and len(nov.violations) > 100 else (nov.violations or 'N/A'),
                'recipient_name': nov.recipient_name or 'N/A',
                'sent_by': self._format_user(nov.sent_by),
                'status': status,
            })
        return rows
    
    def _format_user(self, user):
        """Format user display name"""
        if not user:
            return 'N/A'
        if user.first_name and user.last_name:
            return f"{user.first_name} {user.last_name}"
        return user.email


class NoticeOfOrderReportGenerator(BaseReportGenerator):
    """Generate Notice of Order (NOO) reports"""
    report_type = 'noo'
    report_title = 'Notice of Order Report'
    
    def get_columns(self):
        return [
            {'key': 'inspection_code', 'label': 'Inspection Code'},
            {'key': 'establishment_name', 'label': 'Establishment'},
            {'key': 'law', 'label': 'Law'},
            {'key': 'sent_date', 'label': 'Date Sent'},
            {'key': 'penalty_fees', 'label': 'Penalty Fees'},
            {'key': 'payment_deadline', 'label': 'Payment Deadline'},
            {'key': 'recipient_name', 'label': 'Recipient'},
            {'key': 'sent_by', 'label': 'Sent By'},
            {'key': 'status', 'label': 'Status'},
        ]
    
    def fetch_data(self, date_from, date_to, extra_filters, user):
        queryset = NoticeOfOrder.objects.select_related(
            'inspection_form__inspection',
            'sent_by'
        ).prefetch_related(
            'inspection_form__inspection__establishments'
        )
        
        # Apply date filter on sent_date
        queryset = self.apply_date_filter(queryset, 'sent_date', date_from, date_to)
        
        # Apply extra filters
        if 'law' in extra_filters and extra_filters['law'] != 'ALL':
            queryset = queryset.filter(inspection_form__inspection__law=extra_filters['law'])
        
        if 'establishment_id' in extra_filters and extra_filters['establishment_id']:
            queryset = queryset.filter(inspection_form__inspection__establishments__id=extra_filters['establishment_id'])
        
        if 'sent_by_id' in extra_filters and extra_filters['sent_by_id']:
            queryset = queryset.filter(sent_by__id=extra_filters['sent_by_id'])
        
        if 'status' in extra_filters and extra_filters['status'] != 'ALL':
            # Filter by payment status
            if extra_filters['status'] == 'PENDING':
                queryset = queryset.filter(
                    payment_deadline__gte=datetime.now().date()
                )
            elif extra_filters['status'] == 'OVERDUE':
                queryset = queryset.filter(
                    payment_deadline__lt=datetime.now().date()
                )
        
        if 'min_penalty' in extra_filters and extra_filters['min_penalty']:
            queryset = queryset.filter(penalty_fees__gte=extra_filters['min_penalty'])
        
        if 'max_penalty' in extra_filters and extra_filters['max_penalty']:
            queryset = queryset.filter(penalty_fees__lte=extra_filters['max_penalty'])
        
        return queryset.order_by('-sent_date')
    
    def format_rows(self, data):
        rows = []
        for noo in data:
            inspection = noo.inspection_form.inspection
            establishment_names = ', '.join([est.name for est in inspection.establishments.all()])
            
            # Determine status
            if noo.payment_deadline:
                if noo.payment_deadline < datetime.now().date():
                    status = 'Overdue'
                elif noo.payment_deadline == datetime.now().date():
                    status = 'Due Today'
                else:
                    status = 'Pending'
            else:
                status = 'No Deadline'
            
            rows.append({
                'inspection_code': inspection.code,
                'establishment_name': establishment_names,
                'law': inspection.law,
                'sent_date': noo.sent_date.strftime('%Y-%m-%d') if noo.sent_date else 'Not Sent',
                'penalty_fees': f'₱{noo.penalty_fees:,.2f}' if noo.penalty_fees else '₱0.00',
                'payment_deadline': noo.payment_deadline.strftime('%Y-%m-%d') if noo.payment_deadline else 'N/A',
                'recipient_name': noo.recipient_name or 'N/A',
                'sent_by': self._format_user(noo.sent_by),
                'status': status,
            })
        return rows
    
    def _format_user(self, user):
        """Format user display name"""
        if not user:
            return 'N/A'
        if user.first_name and user.last_name:
            return f"{user.first_name} {user.last_name}"
        return user.email


# Report generator registry
REPORT_GENERATORS = {
    'inspection': InspectionReportGenerator,
    'establishment': EstablishmentReportGenerator,
    'user': UserReportGenerator,
    'billing': BillingReportGenerator,
    'compliance': ComplianceReportGenerator,
    'non_compliant': NonCompliantReportGenerator,
    'quota': QuotaReportGenerator,
    'law': LawReportGenerator,
    'section_accomplishment': SectionAccomplishmentReportGenerator,
    'unit_accomplishment': UnitAccomplishmentReportGenerator,
    'monitoring_accomplishment': MonitoringAccomplishmentReportGenerator,
    'nov': NoticeOfViolationReportGenerator,
    'noo': NoticeOfOrderReportGenerator,
}


def get_generator(report_type):
    """Get the appropriate generator for a report type"""
    generator_class = REPORT_GENERATORS.get(report_type)
    if not generator_class:
        raise ValueError(f"Unknown report type: {report_type}")
    return generator_class()

