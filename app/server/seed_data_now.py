"""
Quick script to seed ReportAccess data
Run with: python manage.py shell < seed_data_now.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from reports.models import ReportAccess

print("Starting ReportAccess seeding...")

# Clear existing data
ReportAccess.objects.all().delete()
print("✓ Cleared existing data")

# Define access mappings
DEFAULT_ACCESS = {
    "Monitoring Personnel": [
        ("inspection", "Inspection Report"),
        ("monitoring_accomplishment", "Monitoring Accomplishment Report")
    ],
    "Unit Head": [
        ("inspection", "Inspection Report"),
        ("compliance", "Compliance Report"),
        ("non_compliant", "Non-Compliant Report"),
        ("unit_accomplishment", "Unit Accomplishment Report"),
        ("nov", "Notice of Violation Report"),
        ("noo", "Notice of Order Report")
    ],
    "Section Chief": [
        ("inspection", "Inspection Report"),
        ("compliance", "Compliance Report"),
        ("non_compliant", "Non-Compliant Report"),
        ("billing", "Billing Report"),
        ("establishment", "Establishment Report"),
        ("section_accomplishment", "Section Accomplishment Report"),
        ("nov", "Notice of Violation Report"),
        ("noo", "Notice of Order Report")
    ],
    "Division Chief": [
        ("user", "User Report"),
        ("establishment", "Establishment Report"),
        ("law", "Law Report"),
        ("quota", "Quota Report"),
        ("billing", "Billing Report"),
        ("compliance", "Compliance Report"),
        ("non_compliant", "Non-Compliant Report"),
        ("inspection", "Inspection Report"),
        ("section_accomplishment", "Section Accomplishment Report"),
        ("unit_accomplishment", "Unit Accomplishment Report"),
        ("monitoring_accomplishment", "Monitoring Accomplishment Report"),
        ("nov", "Notice of Violation Report"),
        ("noo", "Notice of Order Report")
    ],
    "Legal Unit": [
        ("billing", "Billing Report"),
        ("non_compliant", "Non-Compliant Report"),
        ("compliance", "Compliance Report"),
        ("nov", "Notice of Violation Report"),
        ("noo", "Notice of Order Report")
    ],
    "Admin": [
        ("user", "User Report"),
        ("establishment", "Establishment Report"),
        ("law", "Law Report"),
        ("quota", "Quota Report"),
        ("billing", "Billing Report"),
        ("compliance", "Compliance Report"),
        ("non_compliant", "Non-Compliant Report"),
        ("inspection", "Inspection Report"),
        ("section_accomplishment", "Section Accomplishment Report"),
        ("unit_accomplishment", "Unit Accomplishment Report"),
        ("monitoring_accomplishment", "Monitoring Accomplishment Report"),
        ("nov", "Notice of Violation Report"),
        ("noo", "Notice of Order Report")
    ],
}

created_count = 0

for role, reports in DEFAULT_ACCESS.items():
    for report_type, display_name in reports:
        ReportAccess.objects.create(
            role=role,
            report_type=report_type,
            display_name=display_name
        )
        created_count += 1
        print(f"✓ Created: {role} -> {display_name} ({report_type})")

print(f"\n✅ Success! Created {created_count} ReportAccess entries")

# Verify
total = ReportAccess.objects.count()
print(f"\n📊 Total entries in database: {total}")

# Show by role
from django.db.models import Count
roles = ReportAccess.objects.values('role').annotate(count=Count('role')).order_by('role')
print("\n📋 Reports by role:")
for role in roles:
    print(f"  • {role['role']}: {role['count']} reports")

