"""
Django settings for core project.
"""
from datetime import timedelta
from pathlib import Path
import os
from dotenv import load_dotenv
import secrets
import string
try:
    import dj_database_url
    HAS_DJ_DATABASE_URL = True
except ImportError:
    HAS_DJ_DATABASE_URL = False


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env
load_dotenv()

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-rw-#y=jvoa+u33e(!5-f!q%)0fud1%ra3mxt)(q@f&95nequ!0")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DEBUG", "True") == "True"

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "").split(",") if os.getenv("ALLOWED_HOSTS") else []


# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',

    # Your apps
    'users',
    'establishments',
    'notifications',
    'audit',
    'inspections',
    'system',
    'reports',
    'help',
    'laws',
    'django_celery_beat',
]


AUTH_USER_MODEL = 'users.User'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Serve static files in production
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# REST Framework + JWT
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': 'core.pagination.StandardResultsSetPagination',
    'PAGE_SIZE': 20,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.getenv("ACCESS_TOKEN_LIFETIME_MINUTES", 60))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.getenv("REFRESH_TOKEN_LIFETIME_DAYS", 1))),
    "ROTATE_REFRESH_TOKENS": os.getenv("ROTATE_REFRESH_TOKENS", "True") == "True",
    "BLACKLIST_AFTER_ROTATION": os.getenv("BLACKLIST_AFTER_ROTATION", "True") == "True",
}

# Authentication lockout policy (overridable via env or system config)
LOGIN_MAX_FAILED_ATTEMPTS = int(os.getenv("LOGIN_MAX_FAILED_ATTEMPTS", 10))
LOGIN_LOCKOUT_DURATION_MINUTES = int(os.getenv("LOGIN_LOCKOUT_DURATION_MINUTES", 3))
LOGIN_FINAL_ATTEMPTS_WARNING = int(os.getenv("LOGIN_FINAL_ATTEMPTS_WARNING", 3))

# Password generation function
def generate_secure_password(length=8):
    """Generate a secure random password"""
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    while True:
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        if (any(c.islower() for c in password) and 
            any(c.isupper() for c in password) and 
            any(c.isdigit() for c in password)):
            return password

# Email Configuration - Load from environment variables
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True") == "True"
EMAIL_USE_SSL = False
EMAIL_TIMEOUT = 30
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@ierms.com")

ROOT_URLCONF = 'core.urls'

# CORS Configuration
# In production, set CORS_ALLOW_ALL_ORIGINS=False and configure CORS_ALLOWED_ORIGINS
CORS_ALLOW_ALL_ORIGINS = os.getenv("CORS_ALLOW_ALL_ORIGINS", "False") == "True"

CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",  # Vite dev
    "https://iermsdeploy.vercel.app"  # production frontend
]

# Add production frontend URL from environment variable if provided
if os.getenv("FRONTEND_URL"):
    CORS_ALLOWED_ORIGINS.append(os.getenv("FRONTEND_URL"))

# Email Configuration - Using Gmail for development
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
EMAIL_TIMEOUT = 30
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL")

# Email Security & Headers
EMAIL_SUBJECT_PREFIX = '[IERMS] '
EMAIL_HEADERS = {
    'X-Mailer': 'IERMS System v1.0',
    'X-Priority': '3',
    'X-MSMail-Priority': 'Normal',
}

# Email Retry Configuration
EMAIL_RETRY_ATTEMPTS = 3
EMAIL_RETRY_DELAY = 5  # seconds

# Email Verification
EMAIL_VERIFICATION_REQUIRED = True

# If email credentials are not set, fall back to console backend
if not EMAIL_HOST_USER or not EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    print("⚠️  EMAIL CREDENTIALS NOT SET - Using console backend for development")
    print("   To enable email sending, set these environment variables:")
    print("   - EMAIL_HOST_USER (your Gmail address)")
    print("   - EMAIL_HOST_PASSWORD (your Gmail app password)")
    print("   - DEFAULT_FROM_EMAIL (sender email address)")
    print("   Emails will be printed to console instead of sent.")
else:
    print("Email configuration loaded successfully")
    print(f"   SMTP Host: {EMAIL_HOST}:{EMAIL_PORT}")
    print(f"   From Email: {DEFAULT_FROM_EMAIL}")

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'


# Database: prefer MYSQL_PUBLIC_URL if available (Railway), else use individual vars
if HAS_DJ_DATABASE_URL and (os.environ.get('MYSQL_PUBLIC_URL') or os.environ.get('MYSQL_URL')):
    db_url = os.environ.get('MYSQL_PUBLIC_URL') or os.environ.get('MYSQL_URL')
    DATABASES = {'default': dj_database_url.parse(db_url, conn_max_age=600, conn_health_checks=True)}
    DATABASES['default']['OPTIONS'] = {'init_command': "SET sql_mode='STRICT_TRANS_TABLES'", 'charset': 'utf8mb4'}
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.environ.get('MYSQL_DATABASE') or os.environ.get('MYSQLDATABASE'),
            'USER': os.environ.get('MYSQLUSER') or os.environ.get('MYSQL_USER') or 'root',
            'PASSWORD': os.environ.get('MYSQLPASSWORD') or os.environ.get('MYSQL_PASSWORD') or '',
            'HOST': os.environ.get('MYSQLHOST') or os.environ.get('MYSQL_HOST') or '127.0.0.1',
            'PORT': os.environ.get('MYSQLPORT') or os.environ.get('MYSQL_PORT') or '3306',
            'OPTIONS': {'init_command': "SET sql_mode='STRICT_TRANS_TABLES'", 'charset': 'utf8mb4'},
        }
    }



CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = "Asia/Manila"
USE_I18N = True
USE_TZ = True


# Static files
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# WhiteNoise configuration for serving static files
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files (for future use if needed)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Ensure media directory exists
os.makedirs(MEDIA_ROOT, exist_ok=True)

# Default folder for database backups
DEFAULT_BACKUP_DIR = os.path.join(BASE_DIR, "backups")

# Ensure the folder exists
os.makedirs(DEFAULT_BACKUP_DIR, exist_ok=True)

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Celery Configuration: prefer REDIS_URL if available (Railway), else localhost
REDIS_URL = os.getenv('REDIS_URL') or os.getenv('REDIS_PUBLIC_URL') or 'redis://localhost:6379/0'
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True

# Celery Beat Configuration (for scheduled tasks)
CELERY_BEAT_SCHEDULE = {
    'create-scheduled-backup': {
        'task': 'system.tasks.create_scheduled_backup',
        'schedule': None,  # Will be set dynamically based on SystemConfiguration
    },
    'cleanup-old-backups': {
        'task': 'system.tasks.cleanup_old_backups',
        'schedule': 86400.0,  # Run daily at midnight
    },
    'send-nov-compliance-reminders': {
        'task': 'inspections.tasks.send_nov_compliance_reminders',
        'schedule': 86400.0,  # Run daily (every 24 hours)
    },
}

