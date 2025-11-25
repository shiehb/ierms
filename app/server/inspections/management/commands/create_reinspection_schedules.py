"""
Management command to create test reinspection schedules for existing closed inspections
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from inspections.models import Inspection, ReinspectionSchedule
from establishments.models import Establishment
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Create reinspection schedules for existing closed inspections'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Create schedules for ALL closed inspections (not just recent)',
        )

    def handle(self, *args, **options):
        process_all = options.get('all', False)
        
        self.stdout.write("Creating reinspection schedules for closed inspections...")
        
        # Find closed inspections
        closed_inspections = Inspection.objects.filter(
            current_status__in=['CLOSED_COMPLIANT', 'CLOSED_NON_COMPLIANT']
        )
        
        if not process_all:
            # Only process recent closed inspections (last 30 days)
            cutoff_date = timezone.now() - timedelta(days=30)
            closed_inspections = closed_inspections.filter(updated_at__gte=cutoff_date)
        
        self.stdout.write(f"Found {closed_inspections.count()} closed inspections")
        
        created_count = 0
        skipped_count = 0
        
        for inspection in closed_inspections:
            # Determine compliance status and reinspection period
            if inspection.current_status == 'CLOSED_COMPLIANT':
                compliance_status = 'COMPLIANT'
                reinspection_period = timedelta(days=912)  # ~2.5 years
            else:  # CLOSED_NON_COMPLIANT
                compliance_status = 'NON_COMPLIANT'
                reinspection_period = timedelta(days=365)  # 1 year
            
            # Create reinspection schedule for each establishment
            for establishment in inspection.establishments.all():
                # Check if schedule already exists
                existing = ReinspectionSchedule.objects.filter(
                    establishment=establishment,
                    original_inspection=inspection
                ).first()
                
                if existing:
                    skipped_count += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"Schedule already exists for {establishment.name} - {inspection.code}"
                        )
                    )
                    continue
                
                # Calculate due date
                due_date = timezone.now().date() + reinspection_period
                
                # Create schedule
                schedule = ReinspectionSchedule.objects.create(
                    establishment=establishment,
                    original_inspection=inspection,
                    compliance_status=compliance_status,
                    due_date=due_date,
                    status='PENDING'
                )
                
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created schedule for {establishment.name} - Due: {due_date}"
                    )
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f"\nCompleted! Created: {created_count}, Skipped: {skipped_count}"
            )
        )
