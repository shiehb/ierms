# establishments/views.py
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from .models import Establishment
from .serializers import EstablishmentSerializer
from django.db.models import Q
from audit.constants import AUDIT_ACTIONS, AUDIT_MODULES
from audit.utils import log_activity

try:
    from shapely.geometry import Polygon as ShapelyPolygon, MultiPolygon as ShapelyMultiPolygon
    from shapely.ops import unary_union
except Exception:
    ShapelyPolygon = None
    ShapelyMultiPolygon = None
    unary_union = None

User = get_user_model()

class EstablishmentViewSet(viewsets.ModelViewSet):
    queryset = Establishment.objects.all()
    serializer_class = EstablishmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
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
                Q(name__icontains=search) |
                Q(street_building__icontains=search) |
                Q(barangay__icontains=search) |
                Q(city__icontains=search) |
                Q(province__icontains=search) |
                Q(nature_of_business__icontains=search)
            )
        
        # Apply province filter if provided
        province = request.query_params.get('province')
        if province:
            queryset = queryset.filter(province__icontains=province)
        
        # Calculate pagination
        total_count = queryset.count()
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        
        # Apply pagination
        establishments = queryset[start_index:end_index]
        
        # Serialize data
        serializer = self.get_serializer(establishments, many=True)
        
        # Return paginated response
        return Response({
            'count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size,
            'results': serializer.data
        })
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            establishment = serializer.save()

            # Attach the acting user for activity log (for signal-based logging)
            establishment._action_user = request.user
            establishment.save()

            # Enhanced audit trail for establishment creation
            log_activity(
                request.user,
                AUDIT_ACTIONS["CREATE"],
                module=AUDIT_MODULES["ESTABLISHMENTS"],
                description=f"{request.user.email} created establishment: {establishment.name}",
                metadata={
                    "entity_id": establishment.id,
                    "entity_name": establishment.name,
                    "entity_type": "establishment",
                    "status": "success",
                    "nature_of_business": establishment.nature_of_business,
                    "province": establishment.province,
                    "city": establishment.city,
                    "barangay": establishment.barangay,
                    "year_established": establishment.year_established,
                    "is_active": establishment.is_active,
                    "has_polygon": bool(establishment.polygon),
                    "has_marker_icon": bool(establishment.marker_icon),
                },
                request=request,
            )

            # Send notifications to specific user roles
            self.send_establishment_creation_notification(establishment, request.user)
            
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        except Exception as e:
            return Response(
                {'error': str(e) if hasattr(e, 'detail') else serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=kwargs.pop('partial', False))
            serializer.is_valid(raise_exception=True)
            establishment = serializer.save()

            # Attach the acting user for activity log
            establishment._action_user = request.user
            establishment.save()

            return Response(serializer.data)
        except Exception as e:
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data)
            serializer.is_valid(raise_exception=False)
            return Response(
                {'error': str(e) if hasattr(e, 'detail') else serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def send_establishment_creation_notification(self, establishment, created_by):
        # Users who should be notified about new establishments
        notify_userlevels = ["Admin", "Legal Unit", "Division Chief", "Section Chief", "Unit Head"]
        
        # Get all users with these levels
        users_to_notify = User.objects.filter(userlevel__in=notify_userlevels, is_active=True)
        
        for recipient in users_to_notify:
            from notifications.models import Notification
            Notification.objects.create(
                recipient=recipient,
                sender=created_by,
                notification_type='new_establishment',
                title='New Establishment Created',
                message=f'A new establishment "{establishment.name}" has been created by {created_by.email}.'
            )
    
    @action(detail=True, methods=['post'])
    def set_polygon(self, request, pk=None):
        establishment = self.get_object()
        polygon_data = request.data.get('polygon')
        marker_icon = request.data.get('marker_icon')
        
        if polygon_data is not None:
            if not isinstance(polygon_data, list):
                return Response({'error': 'Polygon data must be a list of coordinates'}, status=status.HTTP_400_BAD_REQUEST)
            
            for coord in polygon_data:
                if not isinstance(coord, list) or len(coord) != 2:
                    return Response({'error': 'Each coordinate must be a [lat, lng] pair'}, status=status.HTTP_400_BAD_REQUEST)
                try:
                    float(coord[0]), float(coord[1])
                except (ValueError, TypeError):
                    return Response({'error': 'Coordinates must be valid numbers'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Server-side non-overlap enforcement if shapely available
            result_polygon = polygon_data
            was_adjusted = False
            adjustment_message = ""
            
            if ShapelyPolygon is not None and polygon_data and len(polygon_data) >= 3:
                # Build current polygon
                try:
                    drawn = ShapelyPolygon([(float(lng), float(lat)) for lat, lng in polygon_data])
                except Exception:
                    return Response({'error': 'Invalid polygon geometry'}, status=status.HTTP_400_BAD_REQUEST)
                if not drawn.is_valid or drawn.area == 0:
                    return Response({'error': 'Invalid or empty polygon'}, status=status.HTTP_400_BAD_REQUEST)

                # Collect other establishment polygons
                others = Establishment.objects.exclude(pk=establishment.pk).values_list('polygon', flat=True)
                shapes = []
                for poly in others:
                    if isinstance(poly, list) and len(poly) >= 3:
                        try:
                            shp = ShapelyPolygon([(float(lng), float(lat)) for lat, lng in poly])
                            if shp.is_valid and shp.area > 0:
                                shapes.append(shp)
                        except Exception:
                            continue
                if shapes:
                    union = unary_union(shapes)
                    diff = drawn.difference(union)
                    # Choose largest polygon if multipolygon
                    if diff.is_empty:
                        result_polygon = []
                        was_adjusted = True
                        adjustment_message = "Polygon fully overlapped existing areas and was cleared"
                    elif isinstance(diff, ShapelyPolygon):
                        coords = list(diff.exterior.coords)
                        result_polygon = [[lat, lng] for (lng, lat) in coords[:-1]]
                        if len(result_polygon) < len(polygon_data):
                            was_adjusted = True
                            adjustment_message = "Polygon adjusted to avoid overlaps"
                    else:
                        # MultiPolygon: pick largest by area
                        biggest = None
                        biggest_area = -1
                        for geom in diff.geoms:
                            if geom.area > biggest_area:
                                biggest_area = geom.area
                                biggest = geom
                        if biggest is not None:
                            coords = list(biggest.exterior.coords)
                            result_polygon = [[lat, lng] for (lng, lat) in coords[:-1]]
                            was_adjusted = True
                            adjustment_message = "Polygon adjusted to avoid overlaps - kept largest piece"
                        else:
                            result_polygon = []
                            was_adjusted = True
                            adjustment_message = "No valid polygon pieces found after adjustment"

            establishment.polygon = result_polygon
            
            # Update marker icon if provided
            if marker_icon is not None:
                establishment.marker_icon = marker_icon
            
            establishment._action_user = request.user  # log who updated polygon
            establishment.save()
            return Response({
                'status': 'polygon set', 
                'polygon': establishment.polygon,
                'marker_icon': establishment.marker_icon,
                'was_adjusted': was_adjusted,
                'adjustment_message': adjustment_message
            })
        
        return Response({'error': 'No polygon data provided'}, status=400)
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        active_establishments = Establishment.objects.filter(is_active=True)
        serializer = self.get_serializer(active_establishments, many=True)
        return Response(serializer.data)
    
    # Add this to EstablishmentViewSet
    @action(detail=False, methods=['get'])
    def search(self, request):
        query = request.GET.get('q', '').strip()
        
        if not query or len(query) < 2:
            return Response({'results': [], 'count': 0})
        
        # Simple search across name, address, and business type
        establishments = Establishment.objects.filter(
            Q(name__icontains=query) |
            Q(street_building__icontains=query) |
            Q(barangay__icontains=query) |
            Q(city__icontains=query) |
            Q(province__icontains=query) |
            Q(nature_of_business__icontains=query)
        )
        
        serializer = self.get_serializer(establishments, many=True)
        return Response({
            'results': serializer.data,
            'count': establishments.count()
        })
    
    @action(detail=False, methods=['get'])
    def available_for_inspection(self, request):
        """
        Get establishments that are available for inspection (not currently under active inspection).
        An establishment is considered unavailable if it has any inspection with status not in:
        - CLOSED_COMPLIANT
        - CLOSED_NON_COMPLIANT
        - CREATED (initial state, can be overridden)
        """
        from inspections.models import Inspection
        
        # Get pagination parameters
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 10))
        
        # Get search parameter
        search = request.query_params.get('search', '').strip()
        
        # Get all establishments
        queryset = Establishment.objects.all()
        
        # Apply search filter if provided
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(street_building__icontains=search) |
                Q(barangay__icontains=search) |
                Q(city__icontains=search) |
                Q(province__icontains=search) |
                Q(nature_of_business__icontains=search)
            )
        
        # Exclude establishments that have active inspections
        # Active statuses are all except the final closed states
        active_statuses = [
            'SECTION_ASSIGNED', 'SECTION_IN_PROGRESS', 'SECTION_COMPLETED',
            'UNIT_ASSIGNED', 'UNIT_IN_PROGRESS', 'UNIT_COMPLETED',
            'MONITORING_ASSIGNED', 'MONITORING_IN_PROGRESS', 
            'MONITORING_COMPLETED_COMPLIANT', 'MONITORING_COMPLETED_NON_COMPLIANT',
            'UNIT_REVIEWED', 'SECTION_REVIEWED', 'DIVISION_REVIEWED',
            'LEGAL_REVIEW', 'NOV_SENT', 'NOO_SENT'
        ]
        
        # Get establishment IDs that have active inspections
        active_inspection_establishment_ids = Inspection.objects.filter(
            current_status__in=active_statuses
        ).values_list('establishments', flat=True)
        
        # Exclude establishments with active inspections
        queryset = queryset.exclude(id__in=active_inspection_establishment_ids)
        
        # Calculate pagination
        total_count = queryset.count()
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        
        # Apply pagination
        establishments = queryset[start_index:end_index]
        
        # Serialize data
        serializer = self.get_serializer(establishments, many=True)
        
        return Response({
            'results': serializer.data,
            'count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size
        })
    
    @action(detail=False, methods=['get'])
    def my_establishments(self, request):
        """
        Get establishments based on user role:
        - Admin, Division Chief, Legal Unit: All establishments
        - Section Chief, Unit Head, Monitoring Personnel: Only establishments with active inspections assigned to them
        """
        from inspections.models import Inspection
        
        user = request.user
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 10000))
        
        # Define active inspection statuses (not closed)
        active_statuses = [
            'CREATED',
            'SECTION_ASSIGNED', 'SECTION_IN_PROGRESS', 
            'SECTION_COMPLETED_COMPLIANT', 'SECTION_COMPLETED_NON_COMPLIANT',
            'UNIT_ASSIGNED', 'UNIT_IN_PROGRESS', 
            'UNIT_COMPLETED_COMPLIANT', 'UNIT_COMPLETED_NON_COMPLIANT',
            'MONITORING_ASSIGNED', 'MONITORING_IN_PROGRESS',
            'MONITORING_COMPLETED_COMPLIANT', 'MONITORING_COMPLETED_NON_COMPLIANT',
            'UNIT_REVIEWED', 'SECTION_REVIEWED', 'DIVISION_REVIEWED',
            'LEGAL_REVIEW', 'NOV_SENT', 'NOO_SENT'
        ]
        
        # Role-based filtering
        if user.userlevel in ['Admin', 'Division Chief', 'Legal Unit']:
            # Show all establishments
            queryset = Establishment.objects.all()
        else:
            # Section Chief, Unit Head, Monitoring Personnel
            # Get establishment IDs from active inspections assigned to this user
            # Handle ManyToMany field properly
            inspections = Inspection.objects.filter(
                assigned_to=user,
                current_status__in=active_statuses
            ).prefetch_related('establishments')
            
            # Collect unique establishment IDs from the ManyToMany relationship
            establishment_ids = set()
            for inspection in inspections:
                establishment_ids.update(inspection.establishments.values_list('id', flat=True))
            
            # Filter establishments
            queryset = Establishment.objects.filter(id__in=establishment_ids)
        
        # Apply search if provided
        search = request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(street_building__icontains=search) |
                Q(barangay__icontains=search) |
                Q(city__icontains=search) |
                Q(province__icontains=search) |
                Q(nature_of_business__icontains=search)
            )
        
        # Calculate pagination
        total_count = queryset.count()
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        
        # Apply pagination
        establishments = queryset[start_index:end_index]
        
        # Serialize
        serializer = self.get_serializer(establishments, many=True)
        
        return Response({
            'count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size if page_size > 0 else 1,
            'results': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def location_options(self, request):
        """
        Get location options (provinces and cities) for the establishment forms.
        Returns hardcoded Ilocos Region data as fallback since normalized models may not exist yet.
        """
        # Future: Check if normalized models exist and return from database
        # For now, return empty to use frontend constants
        try:
            # Try to import normalized models
            from .models_normalized import Province, City
            
            # If models exist, return from database
            provinces = Province.objects.filter(is_active=True, region='Ilocos Region').order_by('name')
            cities_by_province = {}
            
            for province in provinces:
                cities = City.objects.filter(province=province, is_active=True).order_by('name')
                cities_by_province[province.name] = [city.name for city in cities]
            
            return Response({
                'provinces': [province.name for province in provinces],
                'cities_by_province': cities_by_province
            })
            
        except ImportError:
            # Normalized models don't exist yet, return empty to use frontend constants
            return Response({
                'provinces': [],
                'cities_by_province': {},
                'message': 'Using frontend constants - normalized models not available'
            })