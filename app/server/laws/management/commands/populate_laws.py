"""
Management command to populate initial laws in the database.
"""
from django.core.management.base import BaseCommand
from laws.models import Law


class Command(BaseCommand):
    help = 'Populate initial environmental laws in the database'

    def handle(self, *args, **options):
        laws_data = [
            {
                'law_title': 'Presidential Decree No. 1586 - Environmental Impact Statement System',
                'reference_code': 'PD-1586',
                'description': 'Environmental Impact Statement System Law - Establishes the Environmental Impact Assessment (EIA) system requiring proponents of environmentally critical projects and projects in environmentally critical areas to prepare environmental impact statements.',
                'category': 'Environmental Impact Assessment',
                'effective_date': '1978-06-11',
                'status': 'Active',
            },
            {
                'law_title': 'Republic Act No. 6969 - Toxic Substances and Hazardous and Nuclear Wastes Control Act',
                'reference_code': 'RA-6969',
                'description': 'Toxic Substances and Hazardous Waste Control Law - Regulates, restricts, or prohibits the importation, manufacture, processing, handling, storage, transportation, sale, distribution, use, and disposal of chemical substances and mixtures that present unreasonable risk or injury to health or the environment.',
                'category': 'Hazardous & Nuclear Waste',
                'effective_date': '1990-10-26',
                'status': 'Active',
            },
            {
                'law_title': 'Republic Act No. 8749 - Philippine Clean Air Act',
                'reference_code': 'RA-8749',
                'description': 'Clean Air Act of the Philippines - Provides for a comprehensive air pollution control policy and program which aims to achieve and maintain healthy air quality levels that will protect human health and the environment.',
                'category': 'Air Quality Management',
                'effective_date': '1999-06-23',
                'status': 'Active',
            },
            {
                'law_title': 'Republic Act No. 9275 - Philippine Clean Water Act',
                'reference_code': 'RA-9275',
                'description': 'Clean Water Act of the Philippines - Provides for the abatement and control of pollution from land-based sources, and lays down water quality standards and regulations.',
                'category': 'Water Quality Management',
                'effective_date': '2004-03-22',
                'status': 'Active',
            },
            {
                'law_title': 'Republic Act No. 9003 - Ecological Solid Waste Management Act',
                'reference_code': 'RA-9003',
                'description': 'Ecological Solid Waste Management Act - Provides for an ecological solid waste management program, creating the necessary institutional mechanisms and incentives, declaring certain acts prohibited and providing penalties.',
                'category': 'Solid Waste Management',
                'effective_date': '2001-01-26',
                'status': 'Active',
            },
        ]

        created_count = 0
        updated_count = 0
        skipped_count = 0

        for law_data in laws_data:
            reference_code = law_data['reference_code']
            
            # Check if law already exists
            existing_law = Law.objects.filter(reference_code=reference_code).first()
            
            if existing_law:
                # Update existing law
                for key, value in law_data.items():
                    setattr(existing_law, key, value)
                existing_law.save()
                updated_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Updated: {reference_code} - {law_data["law_title"]}')
                )
            else:
                # Create new law
                Law.objects.create(**law_data)
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created: {reference_code} - {law_data["law_title"]}')
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\nSummary: {created_count} created, {updated_count} updated, {skipped_count} skipped'
            )
        )


