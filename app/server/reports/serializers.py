from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import AccomplishmentReport, ReportMetric

User = get_user_model()


class ReportMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportMetric
        fields = '__all__'


class AccomplishmentReportSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    metrics = ReportMetricSerializer(read_only=True)
    completed_inspections_count = serializers.SerializerMethodField()
    
    class Meta:
        model = AccomplishmentReport
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']
    
    def get_completed_inspections_count(self, obj):
        return obj.completed_inspections.count()


class AccomplishmentReportListSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    completed_inspections_count = serializers.SerializerMethodField()
    compliance_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = AccomplishmentReport
        fields = [
            'id', 'title', 'report_type', 'quarter', 'year', 'period_start', 'period_end',
            'created_by_name', 'created_at', 'updated_at', 'completed_inspections_count', 'compliance_rate'
        ]
    
    def get_completed_inspections_count(self, obj):
        return obj.completed_inspections.count()
    
    def get_compliance_rate(self, obj):
        if hasattr(obj, 'metrics') and obj.metrics:
            return obj.metrics.compliance_rate
        return 0


class ReportCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccomplishmentReport
        fields = [
            'title', 'report_type', 'quarter', 'year', 'period_start', 'period_end',
            'summary', 'key_achievements', 'completed_inspections'
        ]
    
    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class ReportUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccomplishmentReport
        fields = [
            'title', 'report_type', 'quarter', 'year', 'period_start', 'period_end',
            'summary', 'key_achievements', 'completed_inspections'
        ]
        read_only_fields = ['created_by']
