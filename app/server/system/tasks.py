from celery import shared_task
from django.conf import settings
from django.utils.timezone import now
from datetime import timedelta
import os
import subprocess
import logging
from system.models import BackupRecord
from system.views import get_db_config, get_mysqldump_path, create_sql_backup_python, BACKUP_DIR

logger = logging.getLogger(__name__)


@shared_task
def create_scheduled_backup():
    """Create a scheduled backup with fixed daily schedule"""
    try:
        # Get backup directory from settings or use default
        backup_path = BACKUP_DIR
        
        # Create directory if missing
        os.makedirs(backup_path, exist_ok=True)
        
        # Auto-generate filename: backup_YYYYMMDD_HHMMSS.sql
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"backup_{timestamp}.sql"
        file_path = os.path.join(backup_path, file_name)
        
        db_config = get_db_config()
        db_engine = db_config['engine']
        
        if 'mysql' in db_engine:
            # Try using mysqldump first if available
            mysqldump_path = get_mysqldump_path()
            if mysqldump_path:
                cmd = [mysqldump_path]
                
                if db_config['host'] and db_config['host'] != 'localhost':
                    cmd.extend(["-h", db_config['host']])
                
                if db_config['port'] and db_config['port'] != '3306':
                    cmd.extend(["-P", str(db_config['port'])])
                
                cmd.extend(["-u", db_config['user']])
                
                if db_config['password']:
                    cmd.append(f"-p{db_config['password']}")
                
                cmd.extend([db_config['name']])
                
                try:
                    logger.info(f"Creating scheduled backup: {file_name}")
                    with open(file_path, 'w', encoding='utf-8') as output_file:
                        result = subprocess.run(
                            cmd,
                            stdout=output_file,
                            stderr=subprocess.PIPE,
                            text=True,
                            encoding='utf-8',
                            timeout=300,
                            shell=True
                        )
                    
                    if result.returncode != 0:
                        error_msg = result.stderr if result.stderr else "Unknown mysqldump error"
                        logger.error(f"Scheduled backup failed: {error_msg}")
                        if os.path.exists(file_path):
                            os.remove(file_path)
                        return {"success": False, "error": error_msg}
                        
                except subprocess.TimeoutExpired:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    logger.error("Scheduled backup timed out")
                    return {"success": False, "error": "Backup timed out"}
                except Exception as e:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    logger.error(f"Scheduled backup error: {str(e)}")
                    return {"success": False, "error": str(e)}
            else:
                # Fallback to Python-based SQL backup
                success, message = create_sql_backup_python(db_config, file_path)
                if not success:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    logger.error(f"Scheduled backup failed: {message}")
                    return {"success": False, "error": message}
        else:
            logger.error(f"Unsupported database engine for scheduled backup: {db_engine}")
            return {"success": False, "error": f"Unsupported database: {db_engine}"}
        
        # Verify backup was created
        if not os.path.exists(file_path):
            logger.error("Scheduled backup file was not created")
            return {"success": False, "error": "Backup file was not created"}
        
        # Get file size
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            os.remove(file_path)
            logger.error("Scheduled backup file is empty")
            return {"success": False, "error": "Backup file is empty"}
        
        # Create BackupRecord entry
        try:
            BackupRecord.objects.create(
                fileName=file_name,
                location=backup_path,
                created_at=now()
            )
            logger.info(f"Scheduled backup created successfully: {file_name}")
            return {"success": True, "fileName": file_name, "size": file_size}
        except Exception as e:
            logger.error(f"Failed to create BackupRecord: {str(e)}")
            return {"success": True, "fileName": file_name, "size": file_size, "warning": "Record creation failed"}
        
    except Exception as e:
        logger.error(f"Scheduled backup task error: {str(e)}")
        return {"success": False, "error": str(e)}


@shared_task
def cleanup_old_backups():
    """Delete backups older than retention period"""
    try:
        config = SystemConfiguration.get_active_config()
        retention_days = config.backup_retention_days
        
        cutoff_date = now() - timedelta(days=retention_days)
        
        # Find old backup records
        old_backups = BackupRecord.objects.filter(created_at__lt=cutoff_date)
        
        deleted_count = 0
        for backup_record in old_backups:
            file_path = os.path.join(backup_record.location, backup_record.fileName)
            
            # Delete file if it exists
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.info(f"Deleted old backup file: {backup_record.fileName}")
                except Exception as e:
                    logger.error(f"Failed to delete backup file {backup_record.fileName}: {str(e)}")
                    continue
            
            # Delete record
            backup_record.delete()
            deleted_count += 1
        
        logger.info(f"Cleanup completed: {deleted_count} old backups deleted")
        return {"success": True, "deleted_count": deleted_count}
        
    except Exception as e:
        logger.error(f"Cleanup old backups task error: {str(e)}")
        return {"success": False, "error": str(e)}

