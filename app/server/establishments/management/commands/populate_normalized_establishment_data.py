from django.core.management.base import BaseCommand
from establishments.models_normalized import (
    BusinessType, Province, City, Barangay, 
    EstablishmentStatus, EstablishmentType
)


class Command(BaseCommand):
    help = 'Populates initial data for normalized Establishment models (BusinessType, Province, City, Barangay, EstablishmentStatus, EstablishmentType).'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Populating normalized establishment data...'))

        # Populate BusinessType model
        business_types = [
            {'code': 'MANUFACTURING', 'name': 'Manufacturing', 'category': 'Industrial', 'description': 'Production of goods and materials'},
            {'code': 'SERVICE', 'name': 'Service', 'category': 'Commercial', 'description': 'Provision of services to customers'},
            {'code': 'RETAIL', 'name': 'Retail', 'category': 'Commercial', 'description': 'Sale of goods to end consumers'},
            {'code': 'WHOLESALE', 'name': 'Wholesale', 'category': 'Commercial', 'description': 'Sale of goods in bulk to retailers'},
            {'code': 'AGRICULTURE', 'name': 'Agriculture', 'category': 'Primary', 'description': 'Farming and agricultural activities'},
            {'code': 'MINING', 'name': 'Mining', 'category': 'Primary', 'description': 'Extraction of minerals and resources'},
            {'code': 'CONSTRUCTION', 'name': 'Construction', 'category': 'Industrial', 'description': 'Building and construction activities'},
            {'code': 'TRANSPORTATION', 'name': 'Transportation', 'category': 'Service', 'description': 'Transportation and logistics services'},
            {'code': 'HEALTHCARE', 'name': 'Healthcare', 'category': 'Service', 'description': 'Medical and healthcare services'},
            {'code': 'EDUCATION', 'name': 'Education', 'category': 'Service', 'description': 'Educational services and institutions'},
            {'code': 'FOOD_SERVICE', 'name': 'Food Service', 'category': 'Service', 'description': 'Restaurants and food service establishments'},
            {'code': 'HOSPITALITY', 'name': 'Hospitality', 'category': 'Service', 'description': 'Hotels and accommodation services'},
            {'code': 'ENTERTAINMENT', 'name': 'Entertainment', 'category': 'Service', 'description': 'Entertainment and recreational services'},
            {'code': 'FINANCE', 'name': 'Finance', 'category': 'Service', 'description': 'Financial services and banking'},
            {'code': 'TECHNOLOGY', 'name': 'Technology', 'category': 'Service', 'description': 'Technology and software services'},
            {'code': 'ENVIRONMENTAL', 'name': 'Environmental Services', 'category': 'Service', 'description': 'Environmental protection and management services'},
            {'code': 'WASTE_MANAGEMENT', 'name': 'Waste Management', 'category': 'Service', 'description': 'Waste collection, treatment, and disposal services'},
            {'code': 'WATER_TREATMENT', 'name': 'Water Treatment', 'category': 'Service', 'description': 'Water treatment and purification services'},
            {'code': 'AIR_QUALITY', 'name': 'Air Quality Management', 'category': 'Service', 'description': 'Air quality monitoring and management services'},
            {'code': 'OTHER', 'name': 'Other', 'category': 'Other', 'description': 'Other business types not specified'},
        ]
        
        for bt_data in business_types:
            BusinessType.objects.get_or_create(
                code=bt_data['code'],
                defaults={
                    'name': bt_data['name'],
                    'category': bt_data['category'],
                    'description': bt_data['description']
                }
            )
        self.stdout.write(self.style.SUCCESS('BusinessType model populated.'))

        # Populate Province model
        provinces = [
            {'code': 'LU', 'name': 'La Union', 'region': 'Region I (Ilocos Region)'},
            {'code': 'IN', 'name': 'Ilocos Norte', 'region': 'Region I (Ilocos Region)'},
            {'code': 'IS', 'name': 'Ilocos Sur', 'region': 'Region I (Ilocos Region)'},
            {'code': 'PAN', 'name': 'Pangasinan', 'region': 'Region I (Ilocos Region)'},
            {'code': 'ABRA', 'name': 'Abra', 'region': 'Cordillera Administrative Region (CAR)'},
            {'code': 'APAYAO', 'name': 'Apayao', 'region': 'Cordillera Administrative Region (CAR)'},
            {'code': 'BENGUET', 'name': 'Benguet', 'region': 'Cordillera Administrative Region (CAR)'},
            {'code': 'IFUGAO', 'name': 'Ifugao', 'region': 'Cordillera Administrative Region (CAR)'},
            {'code': 'KALINGA', 'name': 'Kalinga', 'region': 'Cordillera Administrative Region (CAR)'},
            {'code': 'MT', 'name': 'Mountain Province', 'region': 'Cordillera Administrative Region (CAR)'},
        ]
        
        for prov_data in provinces:
            Province.objects.get_or_create(
                code=prov_data['code'],
                defaults={
                    'name': prov_data['name'],
                    'region': prov_data['region']
                }
            )
        self.stdout.write(self.style.SUCCESS('Province model populated.'))

        # Populate Cities for La Union
        lu_province = Province.objects.get(code='LU')
        lu_cities = [
            {'code': 'LU-SFC', 'name': 'San Fernando City', 'city_type': 'CITY'},
            {'code': 'LU-AGOO', 'name': 'Agoo', 'city_type': 'MUNICIPALITY'},
            {'code': 'LU-ARINGAY', 'name': 'Aringay', 'city_type': 'MUNICIPALITY'},
            {'code': 'LU-BACNOTAN', 'name': 'Bacnotan', 'city_type': 'MUNICIPALITY'},
            {'code': 'LU-BAGULIN', 'name': 'Bagulin', 'city_type': 'MUNICIPALITY'},
            {'code': 'LU-BALAOAN', 'name': 'Balaoan', 'city_type': 'MUNICIPALITY'},
            {'code': 'LU-BANGAR', 'name': 'Bangar', 'city_type': 'MUNICIPALITY'},
            {'code': 'LU-BAUANG', 'name': 'Bauang', 'city_type': 'MUNICIPALITY'},
            {'code': 'LU-BURGOS', 'name': 'Burgos', 'city_type': 'MUNICIPALITY'},
            {'code': 'LU-CABA', 'name': 'Caba', 'city_type': 'MUNICIPALITY'},
            {'code': 'LU-LUNA', 'name': 'Luna', 'city_type': 'MUNICIPALITY'},
            {'code': 'LU-NAGUILIAN', 'name': 'Naguilian', 'city_type': 'MUNICIPALITY'},
            {'code': 'LU-PUGO', 'name': 'Pugo', 'city_type': 'MUNICIPALITY'},
            {'code': 'LU-ROSARIO', 'name': 'Rosario', 'city_type': 'MUNICIPALITY'},
            {'code': 'LU-SAN_GABRIEL', 'name': 'San Gabriel', 'city_type': 'MUNICIPALITY'},
            {'code': 'LU-SAN_JUAN', 'name': 'San Juan', 'city_type': 'MUNICIPALITY'},
            {'code': 'LU-SANTO_TOMAS', 'name': 'Santo Tomas', 'city_type': 'MUNICIPALITY'},
            {'code': 'LU-SANTOL', 'name': 'Santol', 'city_type': 'MUNICIPALITY'},
            {'code': 'LU-SUDIPEN', 'name': 'Sudipen', 'city_type': 'MUNICIPALITY'},
            {'code': 'LU-TUBÃO', 'name': 'Tubão', 'city_type': 'MUNICIPALITY'},
        ]
        
        for city_data in lu_cities:
            City.objects.get_or_create(
                code=city_data['code'],
                defaults={
                    'name': city_data['name'],
                    'province': lu_province,
                    'city_type': city_data['city_type']
                }
            )
        self.stdout.write(self.style.SUCCESS('City model populated for La Union.'))

        # Populate some sample barangays for San Fernando City
        sfc_city = City.objects.get(code='LU-SFC')
        sfc_barangays = [
            {'code': 'LU-SFC-001', 'name': 'Bato', 'barangay_type': 'URBAN'},
            {'code': 'LU-SFC-002', 'name': 'Biday', 'barangay_type': 'URBAN'},
            {'code': 'LU-SFC-003', 'name': 'Cabaroan', 'barangay_type': 'URBAN'},
            {'code': 'LU-SFC-004', 'name': 'Carlatan', 'barangay_type': 'URBAN'},
            {'code': 'LU-SFC-005', 'name': 'Catbangen', 'barangay_type': 'URBAN'},
            {'code': 'LU-SFC-006', 'name': 'Dallangayan Este', 'barangay_type': 'URBAN'},
            {'code': 'LU-SFC-007', 'name': 'Dallangayan Oeste', 'barangay_type': 'URBAN'},
            {'code': 'LU-SFC-008', 'name': 'Langcuas', 'barangay_type': 'URBAN'},
            {'code': 'LU-SFC-009', 'name': 'Lingsat', 'barangay_type': 'URBAN'},
            {'code': 'LU-SFC-010', 'name': 'Madayegdeg', 'barangay_type': 'URBAN'},
            {'code': 'LU-SFC-011', 'name': 'Mameltac', 'barangay_type': 'URBAN'},
            {'code': 'LU-SFC-012', 'name': 'Masicong', 'barangay_type': 'URBAN'},
            {'code': 'LU-SFC-013', 'name': 'Nagyubuyuban', 'barangay_type': 'URBAN'},
            {'code': 'LU-SFC-014', 'name': 'Poro', 'barangay_type': 'URBAN'},
            {'code': 'LU-SFC-015', 'name': 'Sagayad', 'barangay_type': 'URBAN'},
            {'code': 'LU-SFC-016', 'name': 'San Agustin', 'barangay_type': 'URBAN'},
            {'code': 'LU-SFC-017', 'name': 'San Antonio', 'barangay_type': 'URBAN'},
            {'code': 'LU-SFC-018', 'name': 'San Francisco', 'barangay_type': 'URBAN'},
            {'code': 'LU-SFC-019', 'name': 'San Vicente', 'barangay_type': 'URBAN'},
            {'code': 'LU-SFC-020', 'name': 'Santiago Norte', 'barangay_type': 'URBAN'},
            {'code': 'LU-SFC-021', 'name': 'Santiago Sur', 'barangay_type': 'URBAN'},
            {'code': 'LU-SFC-022', 'name': 'Sevilla', 'barangay_type': 'URBAN'},
            {'code': 'LU-SFC-023', 'name': 'Tanqui', 'barangay_type': 'URBAN'},
            {'code': 'LU-SFC-024', 'name': 'Tanquigan', 'barangay_type': 'URBAN'},
        ]
        
        for brgy_data in sfc_barangays:
            Barangay.objects.get_or_create(
                code=brgy_data['code'],
                defaults={
                    'name': brgy_data['name'],
                    'city': sfc_city,
                    'barangay_type': brgy_data['barangay_type']
                }
            )
        self.stdout.write(self.style.SUCCESS('Barangay model populated for San Fernando City.'))

        # Populate EstablishmentStatus model
        statuses = [
            {'code': 'ACTIVE', 'name': 'Active', 'description': 'Establishment is currently operating'},
            {'code': 'INACTIVE', 'name': 'Inactive', 'description': 'Establishment is not currently operating'},
            {'code': 'SUSPENDED', 'name': 'Suspended', 'description': 'Establishment operations are suspended'},
            {'code': 'CLOSED', 'name': 'Closed', 'description': 'Establishment has been permanently closed'},
            {'code': 'PENDING', 'name': 'Pending', 'description': 'Establishment status is pending approval'},
            {'code': 'UNDER_REVIEW', 'name': 'Under Review', 'description': 'Establishment is under review'},
            {'code': 'NON_COMPLIANT', 'name': 'Non-Compliant', 'description': 'Establishment is not in compliance with regulations'},
            {'code': 'COMPLIANT', 'name': 'Compliant', 'description': 'Establishment is in compliance with regulations'},
        ]
        
        for status_data in statuses:
            EstablishmentStatus.objects.get_or_create(
                code=status_data['code'],
                defaults={
                    'name': status_data['name'],
                    'description': status_data['description']
                }
            )
        self.stdout.write(self.style.SUCCESS('EstablishmentStatus model populated.'))

        # Populate EstablishmentType model
        establishment_types = [
            {'code': 'CORPORATION', 'name': 'Corporation', 'requires_license': True, 'description': 'Corporate business entity'},
            {'code': 'PARTNERSHIP', 'name': 'Partnership', 'requires_license': True, 'description': 'Partnership business entity'},
            {'code': 'SOLE_PROPRIETORSHIP', 'name': 'Sole Proprietorship', 'requires_license': True, 'description': 'Individual business owner'},
            {'code': 'COOPERATIVE', 'name': 'Cooperative', 'requires_license': True, 'description': 'Cooperative business entity'},
            {'code': 'NON_PROFIT', 'name': 'Non-Profit Organization', 'requires_license': False, 'description': 'Non-profit organization'},
            {'code': 'GOVERNMENT', 'name': 'Government Entity', 'requires_license': False, 'description': 'Government agency or entity'},
            {'code': 'FOREIGN', 'name': 'Foreign Corporation', 'requires_license': True, 'description': 'Foreign business entity'},
            {'code': 'BRANCH', 'name': 'Branch Office', 'requires_license': True, 'description': 'Branch office of a corporation'},
            {'code': 'SUBSIDIARY', 'name': 'Subsidiary', 'requires_license': True, 'description': 'Subsidiary company'},
            {'code': 'FRANCHISE', 'name': 'Franchise', 'requires_license': True, 'description': 'Franchise business'},
        ]
        
        for et_data in establishment_types:
            EstablishmentType.objects.get_or_create(
                code=et_data['code'],
                defaults={
                    'name': et_data['name'],
                    'requires_license': et_data['requires_license'],
                    'description': et_data['description']
                }
            )
        self.stdout.write(self.style.SUCCESS('EstablishmentType model populated.'))

        self.stdout.write(self.style.SUCCESS('All normalized establishment data populated successfully.'))
        
        # Display summary
        self.stdout.write(self.style.SUCCESS('\nSummary:'))
        self.stdout.write(f'Business Types: {BusinessType.objects.count()}')
        self.stdout.write(f'Provinces: {Province.objects.count()}')
        self.stdout.write(f'Cities: {City.objects.count()}')
        self.stdout.write(f'Barangays: {Barangay.objects.count()}')
        self.stdout.write(f'Establishment Statuses: {EstablishmentStatus.objects.count()}')
        self.stdout.write(f'Establishment Types: {EstablishmentType.objects.count()}')
