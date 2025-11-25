# establishments/serializers.py
from rest_framework import serializers
from .models import Establishment
from django.core.exceptions import ValidationError

class EstablishmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Establishment
        fields = '__all__'
    
    def validate(self, data):
        # Check for case-insensitive duplicates
        name = data.get('name')
        if name:
            # For updates, exclude current instance
            instance = self.instance
            queryset = Establishment.objects.filter(name__iexact=name)
            if instance:
                queryset = queryset.exclude(pk=instance.pk)
            
            if queryset.exists():
                raise serializers.ValidationError({
                    'name': ['An establishment with this name already exists.']
                })
        
        # Validate polygon data if provided
        polygon = data.get('polygon')
        if polygon is not None:
            self._validate_polygon(polygon)
        
        return data
    
    def _validate_polygon(self, polygon_data):
        """Validate polygon coordinate data"""
        if polygon_data is None:
            return
        
        if not isinstance(polygon_data, list):
            raise serializers.ValidationError({
                'polygon': ['Polygon data must be a list of coordinates']
            })
        
        if len(polygon_data) > 0 and len(polygon_data) < 3:
            raise serializers.ValidationError({
                'polygon': ['Polygon must have at least 3 points']
            })
        
        for i, coord in enumerate(polygon_data):
            if not isinstance(coord, list) or len(coord) != 2:
                raise serializers.ValidationError({
                    'polygon': [f'Coordinate {i} must be a [lat, lng] pair']
                })
            
            try:
                lat, lng = float(coord[0]), float(coord[1])
                
                # Validate coordinate ranges
                if lat < -90 or lat > 90:
                    raise serializers.ValidationError({
                        'polygon': [f'Coordinate {i} latitude must be between -90 and 90']
                    })
                
                if lng < -180 or lng > 180:
                    raise serializers.ValidationError({
                        'polygon': [f'Coordinate {i} longitude must be between -180 and 180']
                    })
                    
            except (ValueError, TypeError):
                    raise serializers.ValidationError({
                        'polygon': [f'Coordinate {i} must be valid numbers']
                    })


class AdminReportEstablishmentSerializer(serializers.ModelSerializer):
    """Serializer for Admin Report - Establishment data"""
    full_address = serializers.SerializerMethodField()
    
    class Meta:
        model = Establishment
        fields = (
            'id',
            'name',
            'nature_of_business',
            'province',
            'city',
            'barangay',
            'street_building',
            'full_address',
            'created_at',
            'updated_at',
            'is_active'
        )
    
    def get_full_address(self, obj):
        """Get full address formatted"""
        parts = []
        if obj.street_building:
            parts.append(obj.street_building)
        if obj.barangay:
            parts.append(obj.barangay)
        if obj.city:
            parts.append(obj.city)
        if obj.province:
            parts.append(obj.province)
        return ', '.join(parts) if parts else 'N/A'