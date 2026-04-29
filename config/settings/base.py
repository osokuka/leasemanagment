"""
Base Django settings for the project.
"""
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Core settings
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-change-me')
DEBUG = os.environ.get('DEBUG', '0') == '1'
ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    'bm.prosolutions-ks.com',
    'bibaj-management.com',
    'www.bibaj-management.com',
]
ALLOWED_HOSTS += os.environ.get('DJANGO_ALLOWED_HOSTS', '').split(',')
ALLOWED_HOSTS = [h.strip() for h in ALLOWED_HOSTS if h.strip()]

# CSRF trusted origins for production domains
CSRF_TRUSTED_ORIGINS = [
    'https://bm.prosolutions-ks.com',
    'https://bibaj-management.com',
    'https://www.bibaj-management.com',
    'http://localhost:8800',
    'http://127.0.0.1:8800',
]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django_htmx',
    'accounts',
    'locations',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'accounts.middleware.UserLanguageMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'config.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRES_DB', 'bldg_mgm'),
        'USER': os.environ.get('POSTGRES_USER', 'postgres'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', 'postgres'),
        'HOST': os.environ.get('POSTGRES_HOST', 'db'),
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
    }
}

# Custom user model
AUTH_USER_MODEL = 'accounts.User'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en'
LANGUAGES = [
    ('en', 'English'),
    ('sq', 'Shqip'),
    ('de', 'Deutsch'),
    ('fr', 'Français'),
    ('it', 'Italiano'),
]
LOCALE_PATHS = [BASE_DIR / 'locale']
USE_I18N = True
USE_TZ = True
TIME_ZONE = 'UTC'

# Language preference stored in cookie (persists across sessions/browser restarts)
LANGUAGE_COOKIE_NAME = 'django_language'
LANGUAGE_COOKIE_AGE = 365 * 24 * 60 * 60  # 1 year
LANGUAGE_COOKIE_PATH = '/'

# Static files
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'static_root'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Login/Logout
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/users/'
LOGOUT_REDIRECT_URL = '/login/'

# Allow iframes for KESCO portal
X_FRAME_OPTIONS = 'SAMEORIGIN'

# Roles
USER_ROLES = [
    ('super_user', 'Super User'),
    ('admin', 'Admin'),
    ('data_entry_clerk', 'Data Entry Clerk'),
]
