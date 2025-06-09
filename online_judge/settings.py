"""
Django settings for online_judge project.
"""

import os
from pathlib import Path

import os
from google.cloud import aiplatform

# Set once in your app startup
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "credentials/gemini-service-key.json"

aiplatform.init(project="gen-lang-client-0899179119", location="us-central1")

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Security
SECRET_KEY = 'django-insecure-m0ugqpwnmv_4jjl^ljk)fjt^i4tzu6tb@o0%f9+1ecilme%e3#'  # Change in production!
DEBUG = True
ALLOWED_HOSTS = ['*']  # For development only

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core.apps.CoreConfig',
    'widget_tweaks',
]

INSTALLED_APPS += ['django_codemirror6']


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'online_judge.urls'

# Templates
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

WSGI_APPLICATION = 'online_judge.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]

# Media files (user uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom settings
CODE_EXECUTION = {
    'TIME_LIMIT': 5,  # seconds
    'MEMORY_LIMIT': 128,  # MB
    'TEMP_DIR': os.path.join(BASE_DIR, 'tmp'),
}

# Email settings (for password reset, etc.)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'  # For development

# Authentication
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

# Security (for production you should set these)
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False

# Compiler paths (MSYS2 specific)
COMPILER_PATHS = {
    'CPP_COMPILER': r'C:\msys64\mingw64\bin\g++.exe',  # Update if your MSYS2 is installed elsewhere
    'JAVA_COMPILER': 'javac',
    'PYTHON_INTERPRETER': 'python'
}
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')