"""Django settings for the wallpaper API."""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    USE_LOCAL_MEDIA=(bool, True),
    B2_ENDPOINT=(str, ""),
    B2_REGION=(str, ""),
    B2_KEY_ID=(str, ""),
    B2_APP_KEY=(str, ""),
    B2_BUCKET=(str, ""),
    B2_CDN_DOMAIN=(str, ""),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="dev-only-insecure-key-change-me")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "storages",
    "wallpapers",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

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

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        # A project checkout should work without a separately installed database.
        # Deployments can still supply a PostgreSQL URL through DATABASE_URL.
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"

# The API contract serves naive UTC timestamps, so the whole stack stores UTC.
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Media storage -------------------------------------------------------
# USE_LOCAL_MEDIA lets the API run without B2 credentials. In that mode files
# land in ./media and the serializer absolutizes file_path against the request;
# with B2 the storage backend already hands us an absolute public url.

USE_LOCAL_MEDIA = env("USE_LOCAL_MEDIA")

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

if USE_LOCAL_MEDIA:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
else:
    # Backblaze B2 through its S3-compatible API.
    AWS_S3_ENDPOINT_URL = env("B2_ENDPOINT")
    AWS_S3_REGION_NAME = env("B2_REGION")
    AWS_ACCESS_KEY_ID = env("B2_KEY_ID")
    AWS_SECRET_ACCESS_KEY = env("B2_APP_KEY")
    AWS_STORAGE_BUCKET_NAME = env("B2_BUCKET")
    AWS_S3_ADDRESSING_STYLE = "virtual"
    # Public bucket: unsigned urls, so file_path stays clean and cacheable.
    AWS_QUERYSTRING_AUTH = False
    AWS_S3_FILE_OVERWRITE = False
    AWS_DEFAULT_ACL = None

    _cdn_domain = env("B2_CDN_DOMAIN")
    if _cdn_domain:
        AWS_S3_CUSTOM_DOMAIN = _cdn_domain

    STORAGES = {
        "default": {"BACKEND": "storages.backends.s3.S3Storage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }

# --- DRF -----------------------------------------------------------------
# The three feeds are public reads, JSON only, with our own envelope; the
# stock pagination classes do not apply.

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "EXCEPTION_HANDLER": "wallpapers.exceptions.detail_exception_handler",
    "UNAUTHENTICATED_USER": None,
}
