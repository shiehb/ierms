from django.core.management.base import BaseCommand
from inspections.models import Inspection
from users.models import User
from establishments.models import Establishment

class Command(BaseCommand):
    help = 'Test inspection data relationships'

    def handle(self, *args, **options):
        # Get the inspection from the database
        try:
            inspection = Inspection.objects.get(id=9)
            self.stdout.write(f"Inspection found: {inspection.code}")
            self.stdout.write(f"Law: {inspection.law}")
            self.stdout.write(f"District: {inspection.district}")
            self.stdout.write(f"Status: {inspection.current_status}")
            
            # Check created_by relationship
            if inspection.created_by:
                self.stdout.write(f"Created by: {inspection.created_by.first_name} {inspection.created_by.last_name} ({inspection.created_by.email})")
            else:
                self.stdout.write("Created by: None")
            
            # Check assigned_to relationship
            if inspection.assigned_to:
                self.stdout.write(f"Assigned to: {inspection.assigned_to.first_name} {inspection.assigned_to.last_name} ({inspection.assigned_to.email})")
                self.stdout.write(f"Assigned to level: {inspection.assigned_to.userlevel}")
            else:
                self.stdout.write("Assigned to: None")
            
            # Check establishments relationship
            establishments = inspection.establishments.all()
            self.stdout.write(f"Establishments count: {establishments.count()}")
            for est in establishments:
                self.stdout.write(f"  - {est.name} ({est.nature_of_business})")
            
            # Test serializer
            from inspections.serializers import InspectionSerializer
            serializer = InspectionSerializer(inspection)
            data = serializer.data
            self.stdout.write(f"Serializer data keys: {list(data.keys())}")
            self.stdout.write(f"Created by name: {data.get('created_by_name')}")
            self.stdout.write(f"Assigned to name: {data.get('assigned_to_name')}")
            self.stdout.write(f"Establishments detail count: {len(data.get('establishments_detail', []))}")
            
        except Inspection.DoesNotExist:
            self.stdout.write("Inspection with ID 9 not found")
        except Exception as e:
            self.stdout.write(f"Error: {e}")
