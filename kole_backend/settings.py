import mimetypes
import environ
import os
from datetime import timedelta
from pathlib import Path
from django.urls import reverse_lazy

# Explicitly ensure correct MIME types on Windows platforms where the registry may map .css or .js incorrectly
mimetypes.add_type("text/css", ".css", True)
mimetypes.add_type("text/javascript", ".js", True)

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False)
)
environ.Env.read_env(BASE_DIR / '.env')

SILENCED_SYSTEM_CHECKS = ['ckeditor.W001']

# Quick-start development settings - unsuitable for production
SECRET_KEY = env('SECRET_KEY', default='fallback-secret-key-for-dev-only')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['*'])

# Application definition
INSTALLED_APPS = [
    "unfold",
    "unfold.contrib.filters", 
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party
    "ckeditor",
    "ckeditor_uploader",  # Enabled for rich image/media uploads
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',

    # Local apps
    'cloudinary_storage',
    'cloudinary',
    'core',
]

AUTH_USER_MODEL = 'core.User'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'kole_backend.middleware.DevNoCacheMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'kole_backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'kole_backend.wsgi.application'

# Database
DATABASES = {
    'default': env.db('DATABASE_URL', default='sqlite:///' + str(BASE_DIR / 'db.sqlite3'))
}

if DATABASES['default']['ENGINE'] == 'django.db.backends.postgresql':
    DATABASES['default']['ENGINE'] = 'django.db.backends.postgresql'

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
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_DIRS = []

# Media files (User uploads / CKEditor media assets)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Use AppDirectoriesFinder so Django reads Unfold's built-in styles directly from the package
STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]

# Standard storage configuration
STORAGES = {
    "default": {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",  # Cloudinary handles user uploads
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",  # Static files stay local!
    },
}

CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.environ.get('CLOUDINARY_CLOUD_NAME'),
    'API_KEY': os.environ.get('CLOUDINARY_API_KEY'),
    'API_SECRET': os.environ.get('CLOUDINARY_API_SECRET'),
}

from django.templatetags.static import static

# ==========================================
# CKEDITOR CONFIGURATION
# ==========================================
CKEDITOR_BASEPATH = "/static/ckeditor/ckeditor/"
CKEDITOR_UPLOAD_PATH = "uploads/"
CKEDITOR_IMAGE_BACKEND = "pillow"

CKEDITOR_CONFIGS = {
    'default': {
        'skin': 'moono-lisa',
        'toolbar': 'Custom',
        'height': 380,
        'width': '100%',
        'contentsCss': ['/static/core/css/ckeditor_content_dark.css'],
        'toolbar_Custom': [
            ['Bold', 'Italic', 'Underline', 'Strike', 'Subscript', 'Superscript'],
            ['NumberedList', 'BulletedList', '-', 'Outdent', 'Indent', 'Blockquote'],
            ['JustifyLeft', 'JustifyCenter', 'JustifyRight', 'JustifyBlock'],
            ['Link', 'Unlink', 'Anchor'],
            ['Image', 'Table', 'HorizontalRule', 'SpecialChar'],
            ['Format', 'Font', 'FontSize'],
            ['TextColor', 'BGColor'],
            ['Maximize', 'Source'],
        ],
    },
}

# REST Framework & Simple JWT Settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# Celery Configuration
CELERY_BROKER_URL = env('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'

from celery.schedules import crontab
CELERY_BEAT_SCHEDULE = {
    'run-sla-inspector-every-30-minutes': {
        'task': 'core.tasks.sla_inspector_job',
        'schedule': crontab(minute='*/30'),
    },
}

UNFOLD = {
    "SITE_TITLE": "KÓLẸ̀ Backend Situation Room",
    "SITE_HEADER": "KÓLẸ̀",
    "SITE_SYMBOL": "recycling",
    "SHOW_HISTORY": True,
    "SHOW_ALL_APPLICATIONS": False,
    "DASHBOARD_CALLBACK": "kole_backend.dashboard.dashboard_callback",
    "SITE_LOGO": {
        "light": lambda request: static("core/img/kole_logo_light.svg"),
        "dark": lambda request: static("core/img/kole_logo_dark.svg"),
    },
    "SITE_ICON": {
        "light": lambda request: static("core/img/kole_icon.svg"),
        "dark": lambda request: static("core/img/kole_icon.svg"),
    },
    "STYLES": [
        lambda request: static("core/css/admin_custom.css"),
    ],
    "SCRIPTS": [
        lambda request: static("core/js/admin_custom.js"),
    ],
    "COLORS": {
        "primary": {
            "50": "240 253 244",
            "100": "220 252 231",
            "500": "34 197 94",   # KÓLẸ̀ Green Accent
            "600": "22 163 74",
            "700": "21 128 61",
        },
    },
    "SIDEBAR": {
        "navigation": [
            {
                "title": "Authentication & Authorization",
                "separator": True,
                "items": [
                    {
                        "title": "Users",
                        "icon": "person",
                        "link": "/admin/core/user/",
                    },
                    {
                        "title": "Groups",
                        "icon": "group",
                        "link": "/admin/auth/group/",
                    },
                ],
            },
            {
                "title": "Dispatch Operations",
                "separator": True,
                "items": [
                    {
                        "title": "Pickup Requests",
                        "icon": "local_shipping",
                        "link": "/admin/core/pickuprequest/",
                    },
                    {
                        "title": "Collector Profiles",
                        "icon": "badge",
                        "link": "/admin/core/collectorprofile/",
                    },
                    {
                        "title": "Geographic Clusters",
                        "icon": "map",
                        "link": "/admin/core/cluster/",
                    },
                    {
                        "title": "Cluster Assistances",
                        "icon": "handshake",
                        "link": "/admin/core/clusterassistance/",
                    },
                ],
            },
            {
                "title": "Commercial & Community",
                "separator": True,
                "items": [
                    {
                        "title": "Awareness Campaigns",
                        "icon": "campaign",
                        "link": "/admin/core/awarenesscampaign/",
                    },
                    {
                        "title": "Waitlist Entries",
                        "icon": "hourglass_top",
                        "link": "/admin/core/waitlistentry/",
                    },
                    {
                        "title": "Organization Profiles",
                        "icon": "corporate_fare",
                        "link": "/admin/core/organizationprofile/",
                    },
                    {
                        "title": "Evacuation Schedules",
                        "icon": "calendar_month",
                        "link": "/admin/core/evacuationschedule/",
                    },
                ],
            },
            {
                "title": "Finance & Settlement",
                "separator": True,
                "items": [
                    {
                        "title": "User Wallets",
                        "icon": "account_balance_wallet",
                        "link": "/admin/core/wallet/",
                    },
                    {
                        "title": "Ledger Entries",
                        "icon": "receipt_long",
                        "link": "/admin/core/ledgerentry/",
                    },
                ],
            },
        ],
    },
}

CORS_ALLOWED_ORIGINS = [
    "https://app.kole.com.ng",
]