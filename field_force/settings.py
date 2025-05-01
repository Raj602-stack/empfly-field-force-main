import os
from pathlib import Path

import environ
import sentry_sdk
from corsheaders.defaults import default_headers
from django.core.exceptions import ImproperlyConfigured
from sentry_sdk.integrations.django import DjangoIntegration
import psutil

env = environ.Env(DEBUG=(bool, False))
BASE_DIR = Path(__file__).resolve().parent.parent
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))


def read_env_variable(key, default=None):
    try:
        return env(key)
    except ImproperlyConfigured:
        return default
    except Exception as e:
        return default


DEPLOYMENT_TYPE = read_env_variable("DEPLOYMENT_TYPE", "internal")
SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
# DEBUG = True

try:
    ALLOWED_HOSTS = env("ALLOWED_HOSTS").split(" ")
except ImproperlyConfigured:
    ALLOWED_HOSTS = []
except Exception as e:
    ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "corsheaders",
    "drf_yasg",
    "rest_framework",
    "account",
    "api",
    "expense",
    "export",
    "member",
    "organization",
    "trip",
    "form_builder",
    "django_celery_beat",
    "django_celery_results",

    'health_check',
    'health_check.db',                          # stock Django health checkers
    'health_check.contrib.psutil',              # disk and memory utilization; requires psutil
    'health_check.contrib.celery',
    'health_check.contrib.rabbitmq',

]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "field_force.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "field_force.wsgi.application"


# Database
# https://docs.djangoproject.com/en/4.0/ref/settings/#databases

DATABASES = {"default": env.db()}


# Password validation
# https://docs.djangoproject.com/en/4.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.SessionAuthentication",
        "account.authentication.TokenAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
}

# Internationalization
# https://docs.djangoproject.com/en/4.0/topics/i18n/

LANGUAGE_CODE = "en-us"

# TIME_ZONE = "UTC"
TIME_ZONE = "Asia/Kolkata"

USE_I18N = True

USE_TZ = True

# * ----- CORS -----

CORS_REGEX = env("CORS_REGEX")

try:
    TRUSTED_ORIGINS = env("TRUSTED_ORIGINS").split(" ")
except ImproperlyConfigured:
    TRUSTED_ORIGINS = []
except Exception as e:
    TRUSTED_ORIGINS = []

if DEPLOYMENT_TYPE != "internal":

    CORS_ALLOW_CREDENTIALS = True
    CORS_ALLOW_HEADERS = list(default_headers) + [
        "HEALTH-CHECK-AUTH-TOKEN",
    ]

    CORS_ALLOWED_ORIGIN_REGEXES = [CORS_REGEX, "http://127.0.0.1:3000/"]

    CSRF_TRUSTED_ORIGINS = ["http://127.0.0.1:3000"]
    for origin in TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(origin)

    CSRF_COOKIE_SAMESITE = "Strict"
    SESSION_COOKIE_SAMESITE = "Strict"
    CSRF_COOKIE_HTTPONLY = False
    SESSION_COOKIE_HTTPONLY = True

    # ! PROD ONLY
    # CSRF_COOKIE_SECURE = True
    # SESSION_COOKIE_SECURE = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.0/howto/static-files/

STATIC_URL = "/api/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "static")

# Base url to serve media files
MEDIA_URL = "/api/fetch-file/media/"

# Path where media is stored
MEDIA_ROOT = os.path.join(BASE_DIR, "media/")

# Default primary key field type
# https://docs.djangoproject.com/en/4.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "account.User"

UI_DOMAIN_URL = read_env_variable("UI_DOMAIN_URL", "http://localhost:3000/")
EMAIL_HOST = env("EMAIL_HOST")
EMAIL_PORT = env("EMAIL_PORT")
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
EMAIL_SENDER = env("EMAIL_SENDER")
EMAIL_USE_TLS = False
EMAIL_USE_SSL = False
EMAIL_BACKEND = "django_smtp_ssl.SSLEmailBackend"

LOGGING_ENABLED = read_env_variable("LOGGING_ENABLED", True)
if LOGGING_ENABLED:
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "verbose": {"format": "%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d | %(message)s"},
            "simple": {"format": "%(levelname)s %(message)s"},
        },
        "filters": {"require_debug_false": {"()": "django.utils.log.RequireDebugFalse"}},
        "handlers": {
            "console": {
                "level": "DEBUG",
                "class": "logging.StreamHandler",
                "formatter": "simple",
            },
            "log_file": {
                "level": "DEBUG",
                "class": "logging.handlers.RotatingFileHandler",
                "filename": os.path.join(BASE_DIR, "logs/app.log"),
                "maxBytes": 16777216,  # 16 MB
                "formatter": "verbose",
            },
            "request_log_file": {
                "level": "DEBUG",
                "class": "logging.handlers.RotatingFileHandler",
                "filename": os.path.join(BASE_DIR, "logs/django_request.log"),
                "maxBytes": 16777216,  # 16 MB
                "formatter": "verbose",
            },
            "mail_admins": {
                "level": "ERROR",
                "filters": ["require_debug_false"],
                "class": "django.utils.log.AdminEmailHandler",
                "include_html": True,
            },
        },
        "loggers": {
            "django.request": {
                "handlers": ["mail_admins"],
                "level": "ERROR",
                "propagate": False,
            },
            # # Application name
            # "account": {
            #     "handlers": ["log_file", "console"],
            #     "level": "INFO",
            #     "propagate": True,
            # },
        },
        # # Configure logging for EVERYTHING at once
        "root": {"handlers": ["log_file", "console"], "level": "INFO"},
    }

SENTRY_DSN = read_env_variable("SENTRY_DSN")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for performance monitoring.
        # We recommend adjusting this value in production.
        traces_sample_rate=1.0,
        # If you wish to associate users to errors (assuming you are using
        # django.contrib.auth) you may enable sending PII data.
        send_default_pii=True,
    )

# KEY for encryption | decryption
CIPHER_KEY = read_env_variable("CIPHER_KEY")

# CELERY CONF
CELERY_RESULT_BACKEND = "django-db"


APPLICATION_NAME = "ff"

BROKER_URL = env("RABBITMQ_BROKER_URL")

total_memory = psutil.virtual_memory().total
total_memory_mb = total_memory / 1024 / 1024
MIN_FREE_MEMORY = (total_memory_mb * 20) / 100

HEALTH_CHECK = {
    'DISK_USAGE_MAX': 80,  # percent
    'MEMORY_MIN': MIN_FREE_MEMORY,    # in MB
}


COMPRESSED_IMG_FOLDER_PATH = env("COMPRESSED_IMG_FOLDER_PATH")
DB_SAVING_PATH = env("DB_SAVING_PATH")
IMAGE_OPTIMIZER_MAX_RUNTIME_HOUR = float(env("IMAGE_OPTIMIZER_MAX_RUNTIME_HOUR"))

print(f"IMAGE_OPTIMIZER_MAX_RUNTIME_HOUR: {IMAGE_OPTIMIZER_MAX_RUNTIME_HOUR}")
