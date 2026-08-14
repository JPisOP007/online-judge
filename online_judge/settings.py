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
DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 'yes')  # Default to True for local development

if DEBUG:
    SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-unsafe-default-key')
else:
    SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')
    if not SECRET_KEY:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured("DJANGO_SECRET_KEY environment variable is required in production (DEBUG=False).")
_DEFAULT_ALLOWED_HOSTS = [
    "thiran.me", "www.thiran.me", "online-judge-11ld.onrender.com",
    "localhost", "127.0.0.1",
]
# DJANGO_ALLOWED_HOSTS is documented in .env.example and DEPLOYMENT_GUIDE.md but
# was previously ignored here. Entries are added to the defaults rather than
# replacing them, so setting the variable can never knock the live host out of
# the list.
_env_allowed_hosts = [h.strip() for h in os.getenv('DJANGO_ALLOWED_HOSTS', '').split(',') if h.strip()]
ALLOWED_HOSTS = list(dict.fromkeys(_DEFAULT_ALLOWED_HOSTS + _env_allowed_hosts))

# Auto-add Render hostname
_render_url = os.getenv('RENDER_EXTERNAL_URL', '')
if _render_url:
    from urllib.parse import urlparse
    _render_host = urlparse(_render_url).hostname
    if _render_host and _render_host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_render_host)

CSRF_TRUSTED_ORIGINS = ["https://thiran.me", "https://www.thiran.me"]
# Dynamically add Render deployment URL if set
_render_url = os.getenv('RENDER_EXTERNAL_URL', '')
if _render_url:
    CSRF_TRUSTED_ORIGINS.append(_render_url)

# === REST FRAMEWORK CONFIGURATION ===
REST_FRAMEWORK = {
    # ObjectId-aware renderer: MongoDB primary keys are not JSON-serialisable
    # by DRF's default encoder. See core/renderers.py.
    'DEFAULT_RENDERER_CLASSES': [
        'core.renderers.MongoJSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
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
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    # Sits after AuthenticationMiddleware so the rate limiter can key on the
    # authenticated user rather than a spoofable X-Forwarded-For header, and
    # after WhiteNoise so static assets never reach it at all.
    'core.middleware.security.SecurityMiddleware',
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
DEFAULT_MONGODB_NAME = "online_judge"
MONGODB_URI = os.getenv("MONGODB_URI", f"mongodb://localhost:27017/{DEFAULT_MONGODB_NAME}")


def _database_name_from_uri(uri, default=DEFAULT_MONGODB_NAME):
    """Read the database name out of a MongoDB connection string.

    NAME used to be hardcoded, so the database named in MONGODB_URI was
    ignored: pointing the variable at a scratch database still read and wrote
    the production one. The name is the URI's path component; URIs that omit
    it (common for Atlas, where it is optional) keep the default.
    """
    from urllib.parse import urlparse

    path = urlparse(uri).path.lstrip("/")
    return path or default


DATABASES = {
    "default": {
        "ENGINE": "django_mongodb_backend",
        "HOST": MONGODB_URI,
        "NAME": _database_name_from_uri(MONGODB_URI),
    }
}

# === CACHING ===
# Rate limiting lives in this cache. LocMemCache is per-process and is wiped on
# every restart, so with more than one worker each keeps its own counter and the
# limit is effectively multiplied. Redis is already required for Celery, so use
# it when it is configured and fall back to local memory for development.
_cache_redis_url = os.environ.get('REDIS_URL')
if _cache_redis_url:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': _cache_redis_url,
            'TIMEOUT': 300,
        }
    }
else:
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

# Media files configuration
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

STORAGES = {
    "default": {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage" if os.getenv('CLOUDINARY_URL') else "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

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
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
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



# === CELERY CONFIGURATION ===
CELERY_BROKER_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

