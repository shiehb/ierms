import os
import subprocess
import json
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import now
from datetime import datetime, timedelta
import logging
import traceback
from .models import BackupRecord
from audit.constants import AUDIT_ACTIONS, AUDIT_MODULES
from audit.utils import log_activity

logger = logging.getLogger(__name__)

# Directory where backups are stored
BACKUP_DIR = os.path.join(settings.BASE_DIR, "backups")
os.makedirs(BACKUP_DIR, exist_ok=True)

def get_db_config():
    """Get database configuration with fallbacks"""
    db = settings.DATABASES["default"]
    db_engine = db["ENGINE"]
    
    config = {
        'engine': db_engine,
        'name': db['NAME'],
        'user': db.get('USER', ''),
        'password': db.get('PASSWORD', ''),
        'host': db.get('HOST', 'localhost'),
        'port': db.get('PORT', '3306'),
    }
    
    return config

def is_mysql_available():
    """Check if MySQL utilities are available"""
    try:
        # Check if mysqldump is available on Windows
        result = subprocess.run(['where', 'mysqldump'], capture_output=True, text=True, timeout=5, shell=True)
        if result.returncode == 0:
            return True
        
        # Check common MariaDB installation paths
        common_paths = [
            r"C:\Program Files\MariaDB 10.4\bin\mysqldump.exe",
            r"C:\Program Files\MariaDB 10.3\bin\mysqldump.exe",
            r"C:\Program Files\MariaDB 10.2\bin\mysqldump.exe",
            r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe",
            r"C:\Program Files\MySQL\MySQL Server 5.7\bin\mysqldump.exe",
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                return True
                
        return False
    except subprocess.TimeoutExpired:
        logger.warning("MySQL utility check timed out")
        return False
    except Exception as e:
        logger.warning(f"MySQL utility check failed: {str(e)}")
        return False

def get_mysqldump_path():
    """Get the full path to mysqldump if available"""
    try:
        result = subprocess.run(['where', 'mysqldump'], capture_output=True, text=True, timeout=5, shell=True)
        if result.returncode == 0:
            return result.stdout.strip().split('\n')[0]
    except:
        pass
    
    # Check common installation paths
    common_paths = [
        r"C:\Program Files\MariaDB 10.4\bin\mysqldump.exe",
        r"C:\Program Files\MariaDB 10.3\bin\mysqldump.exe",
        r"C:\Program Files\MariaDB 10.2\bin\mysqldump.exe",
        r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe",
        r"C:\Program Files\MySQL\MySQL Server 5.7\bin\mysqldump.exe",
    ]
    
    for path in common_paths:
        if os.path.exists(path):
            return path
    
    return None

def get_mysql_path():
    """Get the full path to mysql client if available"""
    try:
        result = subprocess.run(['where', 'mysql'], capture_output=True, text=True, timeout=5, shell=True)
        if result.returncode == 0:
            return result.stdout.strip().split('\n')[0]
    except:
        pass
    
    # Check common installation paths
    common_paths = [
        r"C:\Program Files\MariaDB 10.4\bin\mysql.exe",
        r"C:\Program Files\MariaDB 10.3\bin\mysql.exe",
        r"C:\Program Files\MariaDB 10.2\bin\mysql.exe",
        r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe",
        r"C:\Program Files\MySQL\MySQL Server 5.7\bin\mysql.exe",
    ]
    
    for path in common_paths:
        if os.path.exists(path):
            return path
    
    return None

def run_django_dumpdata_safe():
    """Run Django dumpdata with safe parameters for older MySQL/MariaDB versions"""
    try:
        # Set environment variables to ensure UTF-8 encoding
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        env['LANG'] = 'en_US.UTF-8'
        env['LC_ALL'] = 'en_US.UTF-8'
        
        # First try without natural keys (which cause issues with older MySQL)
        cmd = [
            "python", "manage.py", 
            "dumpdata", 
            "--indent", "2",
            "--exclude", "contenttypes",
            "--exclude", "auth.permission"
        ]
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            encoding='utf-8',  # Explicitly set UTF-8 encoding
            timeout=120,
            cwd=settings.BASE_DIR,
            shell=True,
            env=env
        )
        
        if result.returncode == 0:
            return True, result.stdout
        else:
            # If that fails, try with even fewer options
            cmd = [
                "python", "manage.py", 
                "dumpdata", 
                "--indent", "2"
            ]
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                encoding='utf-8',  # Explicitly set UTF-8 encoding
                timeout=120,
                cwd=settings.BASE_DIR,
                shell=True,
                env=env
            )
            
            if result.returncode == 0:
                return True, result.stdout
            else:
                return False, result.stderr
                
    except subprocess.TimeoutExpired:
        return False, "Timeout expired"
    except Exception as e:
        return False, str(e)

def create_sql_backup_python(db_config, file_path):
    """Create SQL backup using pure Python without mysqldump"""
    try:
        import pymysql
        
        logger.info("Creating SQL backup using Python...")
        
        # Get database connection parameters
        host = db_config['host'] or 'localhost'
        port = int(db_config['port'] or 3306)
        user = db_config['user']
        password = db_config['password']
        database = db_config['name']
        
        # Connect to database
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            charset='utf8mb4'
        )
        
        with conn.cursor() as cursor, open(file_path, 'w', encoding='utf-8') as f:
            # Write header
            f.write("-- MySQL dump created by Python\n")
            f.write(f"-- Database: {database}\n")
            f.write(f"-- Server: {host}:{port}\n")
            f.write(f"-- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("SET FOREIGN_KEY_CHECKS=0;\n\n")
            
            # Get all tables
            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]
            
            for table in tables:
                f.write(f"--\n-- Table structure for table `{table}`\n--\n")
                f.write(f"DROP TABLE IF EXISTS `{table}`;\n")
                
                # Get table creation script
                cursor.execute(f"SHOW CREATE TABLE `{table}`")
                create_table_sql = cursor.fetchone()[1]
                f.write(f"{create_table_sql};\n\n")
                
                # Get table data
                f.write(f"--\n-- Dumping data for table `{table}`\n--\n")
                cursor.execute(f"SELECT * FROM `{table}`")
                rows = cursor.fetchall()
                
                if rows:
                    # Get column names
                    cursor.execute(f"DESCRIBE `{table}`")
                    columns = [col[0] for col in cursor.fetchall()]
                    
                    for row in rows:
                        values = []
                        for value in row:
                            if value is None:
                                values.append("NULL")
                            elif isinstance(value, (int, float)):
                                values.append(str(value))
                            else:
                                # Escape special characters
                                escaped_value = str(value).replace("'", "''").replace("\\", "\\\\")
                                values.append(f"'{escaped_value}'")
                        
                        insert_sql = f"INSERT INTO `{table}` ({', '.join([f'`{col}`' for col in columns])}) VALUES ({', '.join(values)});\n"
                        f.write(insert_sql)
                
                f.write("\n")
            
            f.write("SET FOREIGN_KEY_CHECKS=1;\n")
            f.write("-- Dump completed\n")
        
        conn.close()
        return True, "SQL backup created successfully"
        
    except ImportError:
        return False, "PyMySQL not installed. Run: pip install pymysql"
    except Exception as e:
        return False, f"Python SQL backup failed: {str(e)}"

def restore_sql_backup_python(db_config, file_path):
    """Restore SQL backup using pure Python without mysql client"""
    try:
        import pymysql
        
        logger.info("Restoring SQL backup using Python...")
        
        # Get database connection parameters
        host = db_config['host'] or 'localhost'
        port = int(db_config['port'] or 3306)
        user = db_config['user']
        password = db_config['password']
        database = db_config['name']
        
        # Connect to database
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            charset='utf8mb4'
        )
        
        with conn.cursor() as cursor, open(file_path, 'r', encoding='utf-8') as f:
            sql_script = f.read()
            
            # Split by semicolons but be careful about semicolons in strings
            statements = []
            current_statement = ""
            in_string = False
            string_char = None
            escaped = False
            
            for char in sql_script:
                if escaped:
                    current_statement += char
                    escaped = False
                elif char == '\\':
                    current_statement += char
                    escaped = True
                elif char in ('"', "'") and not in_string:
                    in_string = True
                    string_char = char
                    current_statement += char
                elif char == string_char and in_string:
                    in_string = False
                    string_char = None
                    current_statement += char
                elif char == ';' and not in_string:
                    statements.append(current_statement.strip())
                    current_statement = ""
                else:
                    current_statement += char
            
            # Add the last statement if any
            if current_statement.strip():
                statements.append(current_statement.strip())
            
            # Execute each statement
            for statement in statements:
                if statement and not statement.startswith('--') and not statement.startswith('/*'):
                    try:
                        cursor.execute(statement)
                    except Exception as e:
                        logger.warning(f"Failed to execute statement: {statement[:100]}... Error: {str(e)}")
                        # Continue with next statement
        
        conn.commit()
        conn.close()
        return True, "SQL restore completed successfully"
        
    except ImportError:
        return False, "PyMySQL not installed. Run: pip install pymysql"
    except Exception as e:
        return False, f"Python SQL restore failed: {str(e)}"

@csrf_exempt
def backup_database(request):
    """Create a database backup in SQL format"""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    actor = getattr(request, "user", None)
    audit_user = actor if getattr(actor, "is_authenticated", False) else None

    try:
        # Parse request body
        if request.content_type == 'application/json':
            try:
                body = json.loads(request.body.decode("utf-8"))
            except json.JSONDecodeError:
                return JsonResponse({"error": "Invalid JSON"}, status=400)
        else:
            body = request.POST
        
        # Require path parameter
        custom_path = body.get("path", "")
        if not custom_path:
            log_activity(
                audit_user,
                AUDIT_ACTIONS["BACKUP"],
                module=AUDIT_MODULES["BACKUP"],
                description="Backup request rejected: missing directory path",
                metadata={
                    "status": "failed",
                    "reason": "missing_path",
                },
                request=request,
            )
            return JsonResponse({"error": "Backup directory path is required"}, status=400)
        
        # Create directory if missing
        os.makedirs(custom_path, exist_ok=True)
        
        # Auto-generate filename: backup_YYYYMMDD_HHMMSS.sql
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"backup_{timestamp}.sql"
        file_path = os.path.join(custom_path, file_name)

        db_config = get_db_config()
        db_engine = db_config['engine']

        if 'mysql' in db_engine:
            # Try using mysqldump first if available
            mysqldump_path = get_mysqldump_path()
            if mysqldump_path:
                # Build mysqldump command for Windows
                cmd = [mysqldump_path]
                
                # Add connection parameters
                if db_config['host'] and db_config['host'] != 'localhost':
                    cmd.extend(["-h", db_config['host']])
                
                if db_config['port'] and db_config['port'] != '3306':
                    cmd.extend(["-P", str(db_config['port'])])
                
                cmd.extend(["-u", db_config['user']])
                
                # Add password if provided
                if db_config['password']:
                    cmd.append(f"-p{db_config['password']}")
                
                cmd.extend([db_config['name']])
                
                # Execute mysqldump and redirect output to file
                try:
                    logger.info(f"Executing mysqldump for database: {db_config['name']}")
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
                            logger.error(f"MySQL dump failed: {error_msg}")
                            # Clean up failed backup file
                            if os.path.exists(file_path):
                                os.remove(file_path)
                            log_activity(
                                audit_user,
                                AUDIT_ACTIONS["BACKUP"],
                                module=AUDIT_MODULES["BACKUP"],
                                description=f"mysqldump backup failed for {db_config['name']}",
                                metadata={
                                    "status": "failed",
                                    "reason": "mysqldump_error",
                                    "error": error_msg,
                                    "file_name": file_name,
                                    "path": file_path,
                                },
                                request=request,
                            )
                            return JsonResponse({
                                "error": f"MySQL backup failed: {error_msg}"
                            }, status=500)
                        
                except subprocess.TimeoutExpired:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    log_activity(
                        audit_user,
                        AUDIT_ACTIONS["BACKUP"],
                        module=AUDIT_MODULES["BACKUP"],
                        description=f"Backup timed out for database {db_config['name']}",
                        metadata={
                            "status": "failed",
                            "reason": "timeout",
                            "file_name": file_name,
                            "path": file_path,
                        },
                        request=request,
                    )
                    return JsonResponse({"error": "Backup timed out after 5 minutes"}, status=500)
                except Exception as e:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    log_activity(
                        audit_user,
                        AUDIT_ACTIONS["BACKUP"],
                        module=AUDIT_MODULES["BACKUP"],
                        description=f"mysqldump raised exception for {db_config['name']}",
                        metadata={
                            "status": "failed",
                            "reason": "mysqldump_exception",
                            "error": str(e),
                            "file_name": file_name,
                            "path": file_path,
                        },
                        request=request,
                    )
                    return JsonResponse({"error": f"MySQL backup error: {str(e)}"}, status=500)
            else:
                # Fallback to Python-based SQL backup
                success, message = create_sql_backup_python(db_config, file_path)
                if not success:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    log_activity(
                        audit_user,
                        AUDIT_ACTIONS["BACKUP"],
                        module=AUDIT_MODULES["BACKUP"],
                        description=f"Python backup failed for database {db_config['name']}",
                        metadata={
                            "status": "failed",
                            "reason": "python_backup_error",
                            "error": message,
                            "file_name": file_name,
                            "path": file_path,
                        },
                        request=request,
                    )
                    return JsonResponse({"error": message}, status=500)
                
        elif 'sqlite3' in db_engine:
            # SQLite backup - simply copy the file
            db_path = db_config['name']
            if not os.path.isabs(db_path):
                db_path = os.path.join(settings.BASE_DIR, db_path)
            
            if not os.path.exists(db_path):
                return JsonResponse({"error": f"SQLite database file not found: {db_path}"}, status=404)
            
            import shutil
            shutil.copy2(db_path, file_path)
        else:
            return JsonResponse({"error": f"Unsupported database for SQL backup: {db_engine}"}, status=400)

        # Verify backup was created
        if not os.path.exists(file_path):
            return JsonResponse({"error": "Backup file was not created"}, status=500)
        
        # Get file size
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            os.remove(file_path)
            return JsonResponse({"error": "Backup file is empty"}, status=500)
        
        # Create BackupRecord entry
        try:
            backup_record = BackupRecord.objects.create(
                fileName=file_name,
                location=custom_path,
                backup_type='backup'
            )
        except Exception as e:
            logger.error(f"Failed to create BackupRecord: {str(e)}")
            # Don't fail the request if record creation fails, but log it
            backup_record = None
        
        log_activity(
            audit_user,
            AUDIT_ACTIONS["BACKUP"],
            module=AUDIT_MODULES["BACKUP"],
            description=f"{getattr(audit_user, 'email', 'System')} created backup {file_name}",
            metadata={
                "status": "success",
                "file_name": file_name,
                "path": file_path,
                "location": custom_path,
                "size_bytes": file_size,
            },
            request=request,
        )

        return JsonResponse({
            "message": "Backup created successfully!",
            "fileName": file_name,
            "filePath": file_path,
            "location": custom_path,
            "size": f"{file_size / 1024:.2f} KB",
            "created_at": backup_record.created_at.isoformat() if backup_record else now().isoformat()
        })

    except Exception as e:
        logger.error(f"Backup error: {str(e)}")
        logger.error(traceback.format_exc())
        log_activity(
            audit_user,
            AUDIT_ACTIONS["BACKUP"],
            module=AUDIT_MODULES["BACKUP"],
            description="Unhandled exception during backup",
            metadata={
                "status": "failed",
                "reason": "exception",
                "error": str(e),
            },
            request=request,
        )
        return JsonResponse({"error": f"Backup failed: {str(e)}"}, status=500)


@csrf_exempt
def restore_database(request):
    """Restore database from uploaded file or existing backup"""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
        
    actor = getattr(request, "user", None)
    audit_user = actor if getattr(actor, "is_authenticated", False) else None

    try:
        file = request.FILES.get("file")
        file_name = None
        backup_record_id = None
        
        # Extract file name or backup record ID from JSON body
        if request.content_type == 'application/json':
            try:
                body = json.loads(request.body.decode("utf-8"))
                file_name = body.get("fileName")
                backup_record_id = body.get("backupRecordId")
            except json.JSONDecodeError:
                pass
        else:
            file_name = request.POST.get("fileName")
            backup_record_id = request.POST.get("backupRecordId")
        
        file_path = None
        original_backup_record = None  # Track original backup record for restore log

        if file:
            # Handle uploaded file
            if not file.name.endswith('.sql'):
                return JsonResponse({"error": "Only .sql files are supported"}, status=400)
                
            file_path = os.path.join(BACKUP_DIR, file.name)
            with open(file_path, "wb+") as dest:
                for chunk in file.chunks():
                    dest.write(chunk)
            file_name = file.name
            # Try to find existing BackupRecord for uploaded file
            try:
                original_backup_record = BackupRecord.objects.get(fileName=file_name)
            except BackupRecord.DoesNotExist:
                original_backup_record = None
                    
        elif backup_record_id:
            # Handle restore by BackupRecord ID
            try:
                original_backup_record = BackupRecord.objects.get(id=backup_record_id)
                file_path = os.path.join(original_backup_record.location, original_backup_record.fileName)
                file_name = original_backup_record.fileName
            except BackupRecord.DoesNotExist:
                return JsonResponse({"error": "Backup record not found"}, status=404)
                
        elif file_name:
            # Handle existing backup file by name (legacy support)
            # Try to find BackupRecord first
            try:
                original_backup_record = BackupRecord.objects.get(fileName=file_name)
                file_path = os.path.join(original_backup_record.location, original_backup_record.fileName)
            except BackupRecord.DoesNotExist:
                # Fallback to old behavior: check default backup directory
                if '..' in file_name or file_name.startswith('/'):
                    log_activity(
                        audit_user,
                        AUDIT_ACTIONS["RESTORE"],
                        module=AUDIT_MODULES["BACKUP"],
                        description="Restore request rejected due to invalid file name",
                        metadata={
                            "status": "failed",
                            "reason": "invalid_file_name",
                            "file_name": file_name,
                        },
                        request=request,
                    )
                    return JsonResponse({"error": "Invalid file name"}, status=400)
                file_path = os.path.join(BACKUP_DIR, file_name)
        else:
            log_activity(
                audit_user,
                AUDIT_ACTIONS["RESTORE"],
                module=AUDIT_MODULES["BACKUP"],
                description="Restore request rejected: no file provided",
                metadata={
                    "status": "failed",
                    "reason": "missing_file",
                },
                request=request,
            )
            return JsonResponse({"error": "No file provided"}, status=400)

        if not os.path.exists(file_path):
            log_activity(
                audit_user,
                AUDIT_ACTIONS["RESTORE"],
                module=AUDIT_MODULES["BACKUP"],
                description="Restore request failed: backup file not found",
                metadata={
                    "status": "failed",
                    "reason": "file_not_found",
                    "file_name": file_name,
                    "path": file_path,
                },
                request=request,
            )
            return JsonResponse({"error": "Backup file not found"}, status=404)

        if not file_path.endswith(".sql"):
            log_activity(
                audit_user,
                AUDIT_ACTIONS["RESTORE"],
                module=AUDIT_MODULES["BACKUP"],
                description="Restore request rejected: invalid file type",
                metadata={
                    "status": "failed",
                    "reason": "invalid_extension",
                    "file_name": file_name,
                },
                request=request,
            )
            return JsonResponse({"error": "Only .sql files are supported"}, status=400)

        db_config = get_db_config()
        db_engine = db_config['engine']

        if 'mysql' in db_engine:
            # Try using mysql client first if available
            mysql_path = get_mysql_path()
            if mysql_path:
                # MySQL restore for Windows
                cmd = [mysql_path]
                
                # Add connection parameters
                if db_config['host'] and db_config['host'] != 'localhost':
                    cmd.extend(["-h", db_config['host']])
                
                if db_config['port'] and db_config['port'] != '3306':
                    cmd.extend(["-P", str(db_config['port'])])
                
                cmd.extend(["-u", db_config['user']])
                
                # Add password if provided
                if db_config['password']:
                    cmd.append(f"-p{db_config['password']}")
                
                cmd.append(db_config['name'])
                
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        result = subprocess.run(cmd, stdin=f, capture_output=True, text=True, encoding='utf-8', timeout=300, shell=True)
                        
                    if result.returncode != 0:
                        error_msg = result.stderr if result.stderr else "Unknown mysql error"
                        log_activity(
                            audit_user,
                            AUDIT_ACTIONS["RESTORE"],
                            module=AUDIT_MODULES["BACKUP"],
                            description=f"MySQL restore failed for {db_config['name']}",
                            metadata={
                                "status": "failed",
                                "reason": "mysql_error",
                                "error": error_msg,
                                "file_name": file_name,
                                "path": file_path,
                            },
                            request=request,
                        )
                        return JsonResponse({
                            "error": f"MySQL restore failed: {error_msg}"
                        }, status=500)
                        
                except subprocess.TimeoutExpired:
                    log_activity(
                        audit_user,
                        AUDIT_ACTIONS["RESTORE"],
                        module=AUDIT_MODULES["BACKUP"],
                        description=f"MySQL restore timed out for {db_config['name']}",
                        metadata={
                            "status": "failed",
                            "reason": "timeout",
                            "file_name": file_name,
                            "path": file_path,
                        },
                        request=request,
                    )
                    return JsonResponse({"error": "Restore timed out after 5 minutes"}, status=500)
            else:
                # Fallback to Python-based SQL restore
                success, message = restore_sql_backup_python(db_config, file_path)
                if not success:
                    log_activity(
                        audit_user,
                        AUDIT_ACTIONS["RESTORE"],
                        module=AUDIT_MODULES["BACKUP"],
                        description=f"Python-based restore failed for {db_config['name']}",
                        metadata={
                            "status": "failed",
                            "reason": "python_restore_error",
                            "error": message,
                            "file_name": file_name,
                            "path": file_path,
                        },
                        request=request,
                    )
                    return JsonResponse({"error": message}, status=500)
                
        elif 'sqlite3' in db_engine:
            log_activity(
                audit_user,
                AUDIT_ACTIONS["RESTORE"],
                module=AUDIT_MODULES["BACKUP"],
                description="Restore request rejected: SQLite engine not supported for SQL restore",
                metadata={
                    "status": "failed",
                    "reason": "unsupported_sqlite_restore",
                    "file_name": file_name,
                    "path": file_path,
                },
                request=request,
            )
            return JsonResponse({"error": "SQLite restore from SQL not supported"}, status=400)
        else:
            log_activity(
                audit_user,
                AUDIT_ACTIONS["RESTORE"],
                module=AUDIT_MODULES["BACKUP"],
                description=f"Restore request rejected: unsupported engine {db_engine}",
                metadata={
                    "status": "failed",
                    "reason": "unsupported_engine",
                    "file_name": file_name,
                    "path": file_path,
                },
                request=request,
            )
            return JsonResponse({"error": f"Unsupported database for SQL restore: {db_engine}"}, status=400)

        # Create new BackupRecord entry for restore activity log
        restore_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        restore_location = original_backup_record.location if original_backup_record else BACKUP_DIR
        original_file_name = original_backup_record.fileName if original_backup_record else file_name
        
        # Generate restore log filename
        # Remove .sql extension, add restore timestamp, then add .sql back
        base_name = original_file_name
        if base_name.endswith('.sql'):
            base_name = base_name[:-4]
        restore_file_name = f"restore_{restore_timestamp}_from_{base_name}.sql"
        
        # Ensure filename is unique (in case of multiple restores)
        counter = 1
        while BackupRecord.objects.filter(fileName=restore_file_name).exists():
            restore_file_name = f"restore_{restore_timestamp}_from_{base_name}_{counter}.sql"
            counter += 1
        
        # Create restore log entry
        try:
            BackupRecord.objects.create(
                fileName=restore_file_name,
                location=restore_location,
                backup_type='restore',
                restored_from=original_backup_record
            )
        except Exception as e:
            logger.error(f"Failed to create restore log BackupRecord: {str(e)}")
            # Don't fail the restore operation if log creation fails
        
        log_activity(
            audit_user,
            AUDIT_ACTIONS["RESTORE"],
            module=AUDIT_MODULES["BACKUP"],
            description=f"{getattr(audit_user, 'email', 'System')} restored database from {file_name}",
            metadata={
                "status": "success",
                "file_name": file_name,
                "path": file_path,
                "backup_record_id": getattr(original_backup_record, 'id', None),
                "restore_record": restore_file_name,
            },
            request=request,
        )
        return JsonResponse({"message": "Database restored successfully!"})

    except Exception as e:
        logger.error(f"Restore error: {str(e)}")
        logger.error(traceback.format_exc())
        log_activity(
            audit_user,
            AUDIT_ACTIONS["RESTORE"],
            module=AUDIT_MODULES["BACKUP"],
            description="Unhandled exception during restore",
            metadata={
                "status": "failed",
                "reason": "exception",
                "error": str(e),
            },
            request=request,
        )
        return JsonResponse({"error": f"Restore failed: {str(e)}"}, status=500)

@csrf_exempt
def download_backup(request, file_name):
    """Download a backup file"""
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
        
    actor = getattr(request, "user", None)
    audit_user = actor if getattr(actor, "is_authenticated", False) else None

    try:
        # Security check: prevent directory traversal
        if '..' in file_name or '/' in file_name or '\\' in file_name:
            log_activity(
                audit_user,
                AUDIT_ACTIONS["EXPORT"],
                module=AUDIT_MODULES["BACKUP"],
                description="Backup download blocked due to invalid file name",
                metadata={
                    "status": "failed",
                    "reason": "invalid_file_name",
                    "file_name": file_name,
                },
                request=request,
            )
            return JsonResponse({"error": "Invalid file name"}, status=400)
        
        # Try to find BackupRecord to get location
        file_path = None
        try:
            backup_record = BackupRecord.objects.get(fileName=file_name)
            file_path = os.path.join(backup_record.location, backup_record.fileName)
        except BackupRecord.DoesNotExist:
            # Fallback to default backup directory
            file_path = os.path.join(BACKUP_DIR, file_name)
        
        if not os.path.exists(file_path):
            log_activity(
                audit_user,
                AUDIT_ACTIONS["EXPORT"],
                module=AUDIT_MODULES["BACKUP"],
                description="Backup download failed: file not found",
                metadata={
                    "status": "failed",
                    "reason": "file_not_found",
                    "file_name": file_name,
                    "path": file_path,
                },
                request=request,
            )
            return JsonResponse({"error": "File not found"}, status=404)
        
        # Ensure it's a backup file
        if not file_name.endswith('.sql'):
            log_activity(
                audit_user,
                AUDIT_ACTIONS["EXPORT"],
                module=AUDIT_MODULES["BACKUP"],
                description="Backup download rejected: invalid file type",
                metadata={
                    "status": "failed",
                    "reason": "invalid_extension",
                    "file_name": file_name,
                },
                request=request,
            )
            return JsonResponse({"error": "Not a backup file"}, status=400)
            
        # Serve the file for download
        with open(file_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/octet-stream')
            response['Content-Disposition'] = f'attachment; filename="{file_name}"'
            log_activity(
                audit_user,
                AUDIT_ACTIONS["EXPORT"],
                module=AUDIT_MODULES["BACKUP"],
                description=f"{getattr(audit_user, 'email', 'System')} downloaded backup {file_name}",
                metadata={
                    "status": "success",
                    "file_name": file_name,
                    "path": file_path,
                },
                request=request,
            )
            return response
            
    except Exception as e:
        logger.error(f"Download backup error: {str(e)}")
        logger.error(traceback.format_exc())
        log_activity(
            audit_user,
            AUDIT_ACTIONS["EXPORT"],
            module=AUDIT_MODULES["BACKUP"],
            description="Unhandled exception during backup download",
            metadata={
                "status": "failed",
                "reason": "exception",
                "error": str(e),
                "file_name": file_name,
            },
            request=request,
        )
        return JsonResponse({"error": f"Download failed: {str(e)}"}, status=500)

def list_backups(request):
    """Return list of all backups from BackupRecord model"""
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
        
    try:
        backups = []
        backup_records = BackupRecord.objects.all()
        
        for record in backup_records:
            file_path = os.path.join(record.location, record.fileName)
            
            # Get file size if file exists
            if os.path.exists(file_path):
                size_bytes = os.path.getsize(file_path)
                if size_bytes >= 1024 * 1024:  # MB
                    size_str = f"{size_bytes / (1024 * 1024):.2f} MB"
                else:  # KB
                    size_str = f"{size_bytes / 1024:.2f} KB"
            else:
                size_bytes = 0
                size_str = "0 KB"
            
            backup_data = {
                "id": record.id,
                "fileName": record.fileName,
                "location": record.location,
                "created_at": record.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "size": size_str,
                "sizeBytes": size_bytes,
                "backup_type": record.backup_type,
                "restored_from": None
            }
            
            # Include restored_from information if available
            if record.restored_from:
                backup_data["restored_from"] = {
                    "id": record.restored_from.id,
                    "fileName": record.restored_from.fileName
                }
            
            backups.append(backup_data)
        
        return JsonResponse({"backups": backups})
    
    except Exception as e:
        logger.error(f"List backups error: {str(e)}")
        logger.error(traceback.format_exc())
        return JsonResponse({"error": f"Failed to list backups: {str(e)}"}, status=500)

@csrf_exempt
def delete_backup(request, file_name):
    """Delete a backup file and its record by name"""
    if request.method not in ["DELETE", "POST"]:
        return JsonResponse({"error": "Method not allowed"}, status=405)
        
    actor = getattr(request, "user", None)
    audit_user = actor if getattr(actor, "is_authenticated", False) else None

    try:
        # Security check: prevent directory traversal
        if '..' in file_name or '/' in file_name or '\\' in file_name:
            log_activity(
                audit_user,
                AUDIT_ACTIONS["DELETE"],
                module=AUDIT_MODULES["BACKUP"],
                description="Backup deletion blocked due to invalid file name",
                metadata={
                    "status": "failed",
                    "reason": "invalid_file_name",
                    "file_name": file_name,
                },
                request=request,
            )
            return JsonResponse({"error": "Invalid file name"}, status=400)
        
        # Find BackupRecord
        try:
            backup_record = BackupRecord.objects.get(fileName=file_name)
            file_path = os.path.join(backup_record.location, backup_record.fileName)
            
            # Delete file if it exists
            if os.path.exists(file_path):
                os.remove(file_path)
            
            # Delete record
            backup_record.delete()
            
            log_activity(
                audit_user,
                AUDIT_ACTIONS["DELETE"],
                module=AUDIT_MODULES["BACKUP"],
                description=f"{getattr(audit_user, 'email', 'System')} deleted backup {file_name}",
                metadata={
                    "status": "success",
                    "file_name": file_name,
                    "path": file_path,
                },
                request=request,
            )
            return JsonResponse({"message": "Backup deleted successfully"})
        except BackupRecord.DoesNotExist:
            # Fallback: try to delete file from default directory
            file_path = os.path.join(BACKUP_DIR, file_name)
            if os.path.exists(file_path):
                if not file_name.endswith('.sql'):
                    log_activity(
                        audit_user,
                        AUDIT_ACTIONS["DELETE"],
                        module=AUDIT_MODULES["BACKUP"],
                        description="Backup deletion rejected: invalid file type",
                        metadata={
                            "status": "failed",
                            "reason": "invalid_extension",
                            "file_name": file_name,
                        },
                        request=request,
                    )
                    return JsonResponse({"error": "Not a backup file"}, status=400)
                os.remove(file_path)
                log_activity(
                    audit_user,
                    AUDIT_ACTIONS["DELETE"],
                    module=AUDIT_MODULES["BACKUP"],
                    description=f"{getattr(audit_user, 'email', 'System')} deleted orphaned backup {file_name}",
                    metadata={
                        "status": "success",
                        "file_name": file_name,
                        "path": file_path,
                    },
                    request=request,
                )
                return JsonResponse({"message": "Backup file deleted successfully (record not found)"})
            log_activity(
                audit_user,
                AUDIT_ACTIONS["DELETE"],
                module=AUDIT_MODULES["BACKUP"],
                description="Backup deletion failed: file not found",
                metadata={
                    "status": "failed",
                    "reason": "file_not_found",
                    "file_name": file_name,
                    "path": file_path,
                },
                request=request,
            )
            return JsonResponse({"error": "Backup not found"}, status=404)
        
    except Exception as e:
        logger.error(f"Delete backup error: {str(e)}")
        logger.error(traceback.format_exc())
        log_activity(
            audit_user,
            AUDIT_ACTIONS["DELETE"],
            module=AUDIT_MODULES["BACKUP"],
            description="Unhandled exception during backup deletion",
            metadata={
                "status": "failed",
                "reason": "exception",
                "error": str(e),
                "file_name": file_name,
            },
            request=request,
        )
        return JsonResponse({"error": f"Delete failed: {str(e)}"}, status=500)