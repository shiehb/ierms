from rest_framework import serializers
from .models import Law


class LawSerializer(serializers.ModelSerializer):
    """
    Serializer for Law model with validation.
    """
    class Meta:
        model = Law
        fields = [
            'id',
            'law_title',
            'reference_code',
            'description',
            'category',
            'effective_date',
            'status',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_law_title(self, value):
        """Validate law title"""
        if len(value.strip()) < 3:
            raise serializers.ValidationError("Law title must be at least 3 characters long.")
        return value.strip()
    
    def validate_description(self, value):
        """Validate description"""
        if len(value.strip()) < 10:
            raise serializers.ValidationError("Description must be at least 10 characters long.")
        return value.strip()
    
    def validate_category(self, value):
        """Validate category"""
        if len(value.strip()) < 2:
            raise serializers.ValidationError("Category must be at least 2 characters long.")
        return value.strip()
    
    def validate_reference_code(self, value):
        """Validate reference code"""
        if value:
            value = value.strip()
            if not value:
                return None
            
            # Check for duplicates (case-insensitive)
            instance_id = self.instance.id if self.instance else None
            existing = Law.objects.filter(
                reference_code__iexact=value
            ).exclude(id=instance_id)
            
            if existing.exists():
                raise serializers.ValidationError(
                    "A law with this reference code already exists."
                )
            
            return value
        return None


