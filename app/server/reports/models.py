from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from establishments.models import Establishment
from inspections.models import Inspection

User = get_user_model()


class AccomplishmentReport(models.Model):
    """
    Model for tracking quarterly accomplishment reports
    """
    REPORT_TYPES = [
        ('quarterly', 'Quarterly Report'),
        ('monthly', 'Monthly Report'),
        ('annual', 'Annual Report'),
        ('custom', 'Custom Period'),
    ]
    
    title = models.CharField(max_length=255, help_text="Report title")
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES, default='quarterly')
    
    # Quarterly period fields
    quarter = models.IntegerField(choices=[(1, 'First Quarter'), (2, 'Second Quarter'), (3, 'Third Quarter'), (4, 'Fourth Quarter')], help_text="Quarter number", default=1)
    year = models.IntegerField(help_text="Year of the report", default=2024)
    
    # Date fields
    period_start = models.DateField(help_text="Start date of the reporting period")
    period_end = models.DateField(help_text="End date of the reporting period")
    
    # Content fields
    summary = models.TextField(help_text="Executive summary of accomplishments", blank=True, null=True)
    key_achievements = models.TextField(help_text="Key achievements during the period", blank=True, null=True)
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_reports')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Completed inspections for this report
    completed_inspections = models.ManyToManyField('inspections.Inspection', blank=True, help_text="Inspections included in this report")
    
    # PDF file for generated reports
    pdf_file = models.FileField(upload_to='reports/', blank=True, null=True, help_text="Generated PDF file")
    status = models.CharField(max_length=20, choices=[('DRAFT', 'Draft'), ('COMPLETED', 'Completed'), ('ARCHIVED', 'Archived')], default='DRAFT')
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Accomplishment Report'
        verbose_name_plural = 'Accomplishment Reports'
    
    def __str__(self):
        return f"Q{self.quarter} {self.year} Accomplishment Report"
    
    def calculate_metrics(self):
        """Auto-calculate all metrics for the report"""
        inspections = self.completed_inspections.all()
        
        # Basic counts
        total = inspections.count()
        compliant = inspections.filter(form__compliance_decision='COMPLIANT').count()
        non_compliant = inspections.filter(form__compliance_decision='NON_COMPLIANT').count()
        
        # Compliance rate
        compliance_rate = (compliant / total * 100) if total > 0 else 0
        
        # Law breakdown
        by_law = {}
        for inspection in inspections:
            law = inspection.law
            by_law[law] = by_law.get(law, 0) + 1
        
        # District breakdown
        by_district = {}
        for inspection in inspections:
            district = inspection.district
            by_district[district] = by_district.get(district, 0) + 1
        
        # Create or update metrics
        metrics, created = ReportMetric.objects.get_or_create(
            report=self,
            defaults={
                'total_inspections': total,
                'compliant_inspections': compliant,
                'non_compliant_inspections': non_compliant,
                'compliance_rate': compliance_rate,
                'by_law_stats': by_law,
                'by_district_stats': by_district,
            }
        )
        
        if not created:
            metrics.total_inspections = total
            metrics.compliant_inspections = compliant
            metrics.non_compliant_inspections = non_compliant
            metrics.compliance_rate = compliance_rate
            metrics.by_law_stats = by_law
            metrics.by_district_stats = by_district
            metrics.save()
        
        return metrics


class ReportMetric(models.Model):
    """
    Model for tracking metrics within a report
    """
    report = models.OneToOneField(AccomplishmentReport, on_delete=models.CASCADE, related_name='metrics')
    
    # Core performance metrics
    total_inspections = models.IntegerField(default=0)
    compliant_inspections = models.IntegerField(default=0)
    non_compliant_inspections = models.IntegerField(default=0)
    compliance_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    
    # Law-specific breakdown (JSON field)
    by_law_stats = models.JSONField(default=dict, help_text="Statistics by law type")
    
    # Geographic distribution
    by_district_stats = models.JSONField(default=dict, help_text="Statistics by district")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Report Metric'
        verbose_name_plural = 'Report Metrics'
    
    def __str__(self):
        return f"Metrics for {self.report.title}"


class ReportAccess(models.Model):
    """
    Defines which user roles have access to which report types
    """
    REPORT_TYPE_CHOICES = [
        ('user', 'User Report'),
        ('establishment', 'Establishment Report'),
        ('law', 'Law Report'),
        ('quota', 'Quota Report'),
        ('billing', 'Billing Report'),
        ('compliance', 'Compliance Report'),
        ('non_compliant', 'Non-Compliant Report'),
        ('inspection', 'Inspection Report'),
        ('section_accomplishment', 'Section Accomplishment Report'),
        ('unit_accomplishment', 'Unit Accomplishment Report'),
        ('monitoring_accomplishment', 'Monitoring Accomplishment Report'),
    ]
    
    ROLE_CHOICES = [
        ('Admin', 'Admin'),
        ('Legal Unit', 'Legal Unit'),
        ('Division Chief', 'Division Chief'),
        ('Section Chief', 'Section Chief'),
        ('Unit Head', 'Unit Head'),
        ('Monitoring Personnel', 'Monitoring Personnel'),
    ]
    
    role = models.CharField(
        max_length=50, 
        choices=ROLE_CHOICES,
        help_text="User role"
    )
    report_type = models.CharField(
        max_length=50, 
        choices=REPORT_TYPE_CHOICES,
        help_text="Report type code"
    )
    display_name = models.CharField(
        max_length=100,
        help_text="Human-readable report name",
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = [('role', 'report_type')]
        ordering = ['role', 'report_type']
        verbose_name = 'Report Access'
        verbose_name_plural = 'Report Access Rules'
        indexes = [
            models.Index(fields=['role']),
            models.Index(fields=['report_type']),
        ]
    
    def __str__(self):
        return f"{self.role} -> {self.get_report_type_display()}"
    
    def save(self, *args, **kwargs):
        # Auto-populate display_name from choices if not provided
        if not self.display_name:
            self.display_name = dict(self.REPORT_TYPE_CHOICES).get(self.report_type, self.report_type)
        super().save(*args, **kwargs)


