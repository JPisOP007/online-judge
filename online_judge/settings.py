"""
Django settings for online_judge project.
"""

import os
import base64
from pathlib import Path
from dotenv import load_dotenv

# === BASE DIR ===
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file
load_dotenv(BASE_DIR / '.env')

# === GROQ API CONFIGURATION ===
# Set this flag to indicate whether AI features are available
AI_FEATURES_ENABLED = False

# Read Groq API key from environment only — never hardcode secrets
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

if GROQ_API_KEY:
    AI_FEATURES_ENABLED = True
else:
    # AI features disabled when key is not provided
    AI_FEATURES_ENABLED = False

# === SECURITY ===
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-unsafe-default-key')
DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 'yes')  # Default to True for local development
ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', 'myoj.work.gd,localhost,127.0.0.1,testserver').split(',')

# Auto-add Render hostname
_render_url = os.getenv('RENDER_EXTERNAL_URL', '')
if _render_url:
    from urllib.parse import urlparse
    _render_host = urlparse(_render_url).hostname
    if _render_host and _render_host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_render_host)

CSRF_TRUSTED_ORIGINS = [
    'https://myoj.work.gd',
    'http://myoj.work.gd',
]
# Dynamically add Render deployment URL if set
_render_url = os.getenv('RENDER_EXTERNAL_URL', '')
if _render_url:
    CSRF_TRUSTED_ORIGINS.append(_render_url)

# === REST FRAMEWORK CONFIGURATION ===
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'core.pagination.StandardResultsSetPagination',
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'PAGE_SIZE': 20,
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour'
    }
}

# === JWT CONFIGURATION ===
from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
}

# === CORS SETTINGS ===
CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', '').split(',') if os.getenv('CORS_ALLOWED_ORIGINS') else [
    'http://localhost:3000',
    'http://myapp.local:3000',
]
CORS_ALLOW_CREDENTIALS = True

# === APPLICATIONS ===
INSTALLED_APPS = [
    'online_judge.apps.MongoAdminConfig',
    'online_judge.apps.MongoAuthConfig',
    'online_judge.apps.MongoContentTypesConfig',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'cloudinary_storage',
    'cloudinary',
    'core.apps.CoreConfig',
    'widget_tweaks',
    'django_codemirror6',
    'corsheaders',
    'drf_spectacular',
    'rest_framework',
    'rest_framework_simplejwt',
]

# === MIDDLEWARE ===
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'core.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.security.CodeExecutionSecurityMiddleware',
]

# === URLS & WSGI ===
ROOT_URLCONF = 'online_judge.urls'
WSGI_APPLICATION = 'online_judge.wsgi.application'

# === TEMPLATES ===
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# === DATABASE ===
import os
import certifi

# MongoDB configuration (django-mongodb-backend >= 6.0.x)
DATABASES = {
    "default": {
        "ENGINE": "django_mongodb_backend",
        "HOST": os.getenv(
            "MONGODB_URI",
            "mongodb://localhost:27017/online_judge"
        ),
        # Ensure the DB name is set (MongoDB uses the path component of the URI)
        "NAME": "online_judge",
    }
}

# === CACHING ===
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
        'TIMEOUT': 300,
        'OPTIONS': {
            'MAX_ENTRIES': 1000,
        }
    }
}

# === PASSWORD VALIDATION ===
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# === I18N / TIMEZONE ===
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# === STATIC & MEDIA ===
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')] if os.path.exists(os.path.join(BASE_DIR, 'static')) else []
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files configuration
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

if os.getenv('CLOUDINARY_URL'):
    DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

# File upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
FILE_UPLOAD_PERMISSIONS = 0o644

# === DEFAULT PRIMARY KEY FIELD ===
DEFAULT_AUTO_FIELD = 'django_mongodb_backend.fields.ObjectIdAutoField'

# === CODE EXECUTION CONFIG ===
CODE_EXECUTION = {
    'TIME_LIMIT': 5,
    'MEMORY_LIMIT': 128,
    'TEMP_DIR': os.path.join(BASE_DIR, 'tmp'),
    'MAX_FILE_SIZE': 1024 * 1024,  # 1MB
    'MAX_OUTPUT_SIZE': 1024 * 1024,  # 1MB
    'ALLOWED_LANGUAGES': ['python', 'cpp', 'java', 'javascript'],
}

# === SECURITY SETTINGS ===
# Rate limiting and request size limits
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000
DATA_UPLOAD_MAX_NUMBER_FILES = 20

# Logging configuration for security monitoring
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'WARNING',
            'class': 'logging.StreamHandler',  # Console logging for Render (ephemeral disk)
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django.security': {
            'handlers': ['file', 'console'],
            'level': 'WARNING',
            'propagate': True,
        },
        'core.security': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# === AUTH & EMAIL ===
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

# === SECURITY HEADERS ===
# Production security settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Cookie security
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'

# SSL settings
SECURE_SSL_REDIRECT = not DEBUG
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# === COMPILER PATHS ===
# For containerized Linux, these paths should point to Linux executables
COMPILER_PATHS = {
    'CPP_COMPILER': 'g++',
    'JAVA_COMPILER': 'javac',
    'PYTHON_INTERPRETER': 'python3',
}


