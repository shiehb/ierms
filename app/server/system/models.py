from django.db import models
from django.utils import timezone

class BackupRecord(models.Model):
    """Model to track database backup records"""
    
    BACKUP_TYPE_CHOICES = [
        ('backup', 'Backup'),
        ('restore', 'Restore'),
    ]
    
    fileName = models.CharField(max_length=255, unique=True, help_text="Backup filename in format backup_YYYYMMDD_HHMMSS.sql")
    location = models.CharField(max_length=500, help_text="Full directory path where backup is stored")
    created_at = models.DateTimeField(auto_now_add=True, help_text="When backup was created")
    backup_type = models.CharField(max_length=10, choices=BACKUP_TYPE_CHOICES, default='backup', help_text="Type of record: backup or restore")
    restored_from = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='restore_logs', help_text="Reference to original backup if this is a restore log entry")
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Backup Record"
        verbose_name_plural = "Backup Records"
    
    def __str__(self):
        return f"{self.fileName} ({self.location})"