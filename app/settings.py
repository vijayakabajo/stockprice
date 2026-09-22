import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

# ------------------------------------------------------------------------------
# Project Basic Configuration
# ------------------------------------------------------------------------------
PROJECT_NAME = os.getenv("PROJECT_NAME", "shareprice")
BASE_DIR = Path(__file__).resolve().parent.parent

# Step 1: Loading base .env file (for ENV_TYPE)
load_dotenv(dotenv_path=BASE_DIR / ".env")

# Step 2: Getting environment type
ENV_TYPE = os.getenv("ENV_TYPE", "local").lower()

# Step 3: Loading respective credentials
SECRETS_FILE_MAP = {
    "local": "secrets/.env.local.secrets",
    "preproduction": "secrets/.env.preproduction.secrets",
    "production": "secrets/.env.production.secrets",
}

# Step 4: Loading secrets (missing file is fine locally — .env already has what's needed)
secret_file = SECRETS_FILE_MAP.get(ENV_TYPE)
if secret_file is None:
    raise Exception(f"Unknown ENV_TYPE: {ENV_TYPE}")
load_dotenv(dotenv_path=BASE_DIR / secret_file, override=True)

DEBUG = os.getenv("DEBUG", "False") == "True"
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY not set in environment variables")


# ------------------------------------------------------------------------------
# Hosts, CORS & Middleware
# ------------------------------------------------------------------------------
from app.config.cors import (
    ALLOWED_HOSTS,
    CORS_ALLOW_ALL_ORIGINS,
    CORS_ALLOW_HEADERS,
    CORS_ALLOW_METHODS,
    CSRF_TRUSTED_ORIGINS,
    MIDDLEWARE,
)

# ------------------------------------------------------------------------------
# Installed Apps
# ------------------------------------------------------------------------------

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
]

LOCAL_APPS = [
    "core",
    "accounts",
    "market",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

AUTH_USER_MODEL = "accounts.User"

# ------------------------------------------------------------------------------
# Caching (Redis)
# ------------------------------------------------------------------------------
from app.config.redis import get_cache_config

CACHES = get_cache_config(ENV_TYPE)

# ------------------------------------------------------------------------------
# REST Framework / JWT
# ------------------------------------------------------------------------------
from app.config.rest_framework import get_rest_framework_config

REST_FRAMEWORK = get_rest_framework_config()

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
}

# ------------------------------------------------------------------------------
# URL & WSGI
# ------------------------------------------------------------------------------

ROOT_URLCONF = "app.urls"
WSGI_APPLICATION = "app.wsgi.application"

# ------------------------------------------------------------------------------
# Templates
# ------------------------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ------------------------------------------------------------------------------
# Database
# ------------------------------------------------------------------------------
from app.config.database import get_database_config

DATABASES = get_database_config()

# ------------------------------------------------------------------------------
# Password Validators
# ------------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ------------------------------------------------------------------------------
# Email Settings
# ------------------------------------------------------------------------------

EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", default="")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", default="")
EMAIL_USERNAME = os.getenv("EMAIL_USERNAME", default="")
EMAIL_PORT = os.getenv("EMAIL_PORT", default="")
EMAIL_SMTP_SERVER = os.getenv("EMAIL_SMTP_SERVER", default="")
DOMAIN_SENDER_ADDRESS = os.getenv("DOMAIN_SENDER_ADDRESS", default="")

SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", default="")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", default="")

# ------------------------------------------------------------------------------
# Time & Localization
# ------------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# ------------------------------------------------------------------------------
# Static & Media Files
# ------------------------------------------------------------------------------

# This is an API backend: the only static files are the ones Django admin and
# DRF's browsable API ship with, collected here by `collectstatic`.
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

STATIC_URL = "/static/"
MEDIA_URL = "/media/"

# ------------------------------------------------------------------------------
# Default Auto Field
# ------------------------------------------------------------------------------

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ------------------------------------------------------------------------------
# Application Logger
# ------------------------------------------------------------------------------
from app.config.logger import get_logging_config

LOGGING = get_logging_config(ENV_TYPE, BASE_DIR)

# ------------------------------------------------------------------------------
# Celery
# ------------------------------------------------------------------------------
from app.config.celery import get_celery_config as _get_celery_config

_celery_conf = _get_celery_config(ENV_TYPE)

CELERY_BROKER_URL = _celery_conf["broker_url"]
CELERY_RESULT_BACKEND = _celery_conf["result_backend"]
CELERY_TASK_SERIALIZER = _celery_conf["task_serializer"]
CELERY_RESULT_SERIALIZER = _celery_conf["result_serializer"]
CELERY_ACCEPT_CONTENT = _celery_conf["accept_content"]
CELERY_TIMEZONE = _celery_conf["timezone"]
CELERY_ENABLE_UTC = _celery_conf["enable_utc"]
CELERY_TASK_ACKS_LATE = _celery_conf["task_acks_late"]
CELERY_TASK_REJECT_ON_WORKER_LOST = _celery_conf["task_reject_on_worker_lost"]
CELERY_RESULT_EXPIRES = _celery_conf["result_expires"]
CELERY_BEAT_SCHEDULE = _celery_conf["beat_schedule"]

CELERY_QUEUE_NAME = {
    "production": f"{PROJECT_NAME}_prod",
    "preproduction": f"{PROJECT_NAME}_preprod",
}.get(
    ENV_TYPE, "celery"
)  # local / fallback -> default Celery queue

CELERY_TASK_DEFAULT_QUEUE = CELERY_QUEUE_NAME
CELERY_TASK_DEFAULT_EXCHANGE = CELERY_QUEUE_NAME
CELERY_TASK_DEFAULT_ROUTING_KEY = CELERY_QUEUE_NAME

HOST_URL = os.getenv("HOST_URL", default="")
