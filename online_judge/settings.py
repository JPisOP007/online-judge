"""
Django settings for online_judge project.
"""

import os
import base64
from pathlib import Path
from google.cloud import aiplatform

# === GOOGLE CREDENTIALS (Cloud and Local) ===
encoded_key = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_B64")
if encoded_key:
    try:
        service_account_path = "/tmp/gemini-service-key.json"
        with open(service_account_path, "wb") as f:
            f.write(base64.b64decode(encoded_key))
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account_path
    except Exception as e:
        raise Exception("Failed to decode or write GOOGLE_APPLICATION_CREDENTIALS_B64") from e
else:
    # Fallback for local development
    local_creds = os.path.join(Path(__file__).resolve().parent.parent, "credentials", "gemini-service-key.json")
    if os.path.exists(local_creds):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = local_creds
    else:
        raise EnvironmentError("Google credentials not found for cloud or local setup.")

# Initialize Vertex AI
aiplatform.init(project="gen-lang-client-0899179119", location="us-central1")

# === BASE DIR ===
BASE_DIR = Path(__file__).resolve().parent.parent

# === SECURITY ===
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-unsafe-default-key')
DEBUG = os.getenv('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', '*').split()

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
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
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

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# === DEFAULT PRIMARY KEY FIELD ===
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# === CODE EXECUTION CONFIG ===
CODE_EXECUTION = {
    'TIME_LIMIT': 5,
    'MEMORY_LIMIT': 128,
    'TEMP_DIR': os.path.join(BASE_DIR, 'tmp'),
}

# === AUTH & EMAIL ===
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

# === SECURITY (Adjust in production) ===
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False

# === COMPILER PATHS (for local dev) ===
COMPILER_PATHS = {
    'CPP_COMPILER': r'C:\msys64\mingw64\bin\g++.exe',  # Update if needed
    'JAVA_COMPILER': 'javac',
    'PYTHON_INTERPRETER': 'python'
}
