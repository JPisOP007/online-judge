"""
Django settings for online_judge project.
"""

import os
import base64
from pathlib import Path
from google.cloud import aiplatform

# === BASE DIR ===
BASE_DIR = Path(__file__).resolve().parent.parent

# === GOOGLE CREDENTIALS (Cloud and Local) ===
encoded_key = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_B64")
if encoded_key:
    try:
        service_account_path = "/app/gemini-service-key.json"
        with open(service_account_path, "wb") as f:
            f.write(base64.b64decode(encoded_key))
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account_path
    except Exception as e:
        raise Exception("Failed to decode or write GOOGLE_APPLICATION_CREDENTIALS_B64") from e
else:
    # Fallback for local development
    local_creds = os.path.join(BASE_DIR, "credentials", "gemini-service-key.json")
    if os.path.exists(local_creds):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = local_creds
    else:
        raise EnvironmentError("Google credentials not found for cloud or local setup.")

# Initialize Vertex AI
aiplatform.init(project="gen-lang-client-0899179119", location="us-central1")

# === SECURITY ===
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-unsafe-default-key')
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', 'myoj.work.gd,localhost,127.0.0.1').split(',')

CSRF_TRUSTED_ORIGINS = [
    'https://myoj.work.gd',
    'http://myoj.work.gd',
]

# === APPLICATIONS ===
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core.apps.CoreConfig',
    'widget_tweaks',
    'django_codemirror6',
]

# === MIDDLEWARE ===
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'core.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
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
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
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

# File upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
FILE_UPLOAD_PERMISSIONS = 0o644

# === DEFAULT PRIMARY KEY FIELD ===
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

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
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'security.log'),
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


