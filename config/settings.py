"""Django settings for the wallpaper API."""

from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    CSRF_TRUSTED_ORIGINS=(list, []),
    RAILWAY_PUBLIC_DOMAIN=(str, ""),
    SECURE_SSL_REDIRECT=(bool, False),
    SECURE_HSTS_SECONDS=(int, 0),
    USE_LOCAL_MEDIA=(bool, True),
    B2_ENDPOINT=(str, ""),
    B2_REGION=(str, ""),
    B2_KEY_ID=(str, ""),
    B2_APP_KEY=(str, ""),
    B2_BUCKET=(str, ""),
    B2_CDN_DOMAIN=(str, ""),
    B2_SIGNED_URLS=(bool, False),
    B2_URL_EXPIRE_SECONDS=(int, 3600),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="dev-only-insecure-key-change-me")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")

# --- Railway -------------------------------------------------------------
# Railway injects RAILWAY_PUBLIC_DOMAIN at runtime, so the deployed host does
# not have to be known (or redeployed) when the domain changes.
RAILWAY_PUBLIC_DOMAIN = env("RAILWAY_PUBLIC_DOMAIN")
if RAILWAY_PUBLIC_DOMAIN:
    ALLOWED_HOSTS = [
        *ALLOWED_HOSTS,
        RAILWAY_PUBLIC_DOMAIN,
        # Railway's deploy health check calls the app with this Host header;
        # without it the check gets a 400 and the deploy is rolled back.
        "healthcheck.railway.app",
    ]
    CSRF_TRUSTED_ORIGINS = [*CSRF_TRUSTED_ORIGINS, f"https://{RAILWAY_PUBLIC_DOMAIN}"]

# Railway terminates TLS at its edge and forwards plain HTTP inward. Without
# this Django reads every request as insecure: admin login over https fails the
# CSRF origin check, and build_absolute_uri() would put http:// into file_path.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

if not DEBUG:
    # The admin session is the only thing worth stealing here, and in
    # production it is always reached over https.
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # Both of the following stay opt-in. A blanket redirect can make Railway's
    # health check follow a 301 and fail the deploy, and HSTS is effectively
    # irreversible for the length of its max-age - turn them on deliberately,
    # once a custom domain is settled and serving https only.
    SECURE_SSL_REDIRECT = env("SECURE_SSL_REDIRECT")
    SECURE_REDIRECT_EXEMPT = [r"^api/v1/wallpapers/categories/?$"]
    SECURE_HSTS_SECONDS = env("SECURE_HSTS_SECONDS")

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
    # Railway runs no separate web server, so WhiteNoise serves the admin's
    # static files straight from the app process.
    "whitenoise.middleware.WhiteNoiseMiddleware",
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
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
    }
else:
    # Backblaze B2 through its S3-compatible API.
    AWS_S3_ENDPOINT_URL = env("B2_ENDPOINT")
    AWS_S3_REGION_NAME = env("B2_REGION")
    AWS_ACCESS_KEY_ID = env("B2_KEY_ID")
    AWS_SECRET_ACCESS_KEY = env("B2_APP_KEY")
    AWS_STORAGE_BUCKET_NAME = env("B2_BUCKET")
    AWS_S3_ADDRESSING_STYLE = "virtual"
    AWS_S3_FILE_OVERWRITE = False
    AWS_DEFAULT_ACL = None
    # Bypass machine-wide proxy variables for direct B2 uploads.  A stale
    # localhost proxy otherwise makes botocore close the request before B2
    # can respond.
    AWS_S3_PROXIES = {}

    # A public bucket serves plain urls that never expire, which is what the
    # API contract promises. A private one has to sign every url instead:
    # file_path then carries a signature and dies after B2_URL_EXPIRE_SECONDS,
    # so it cannot be cached by the app or a CDN and must be re-fetched from
    # the API before each use.
    B2_SIGNED_URLS = env("B2_SIGNED_URLS")
    AWS_QUERYSTRING_AUTH = B2_SIGNED_URLS
    AWS_QUERYSTRING_EXPIRE = env("B2_URL_EXPIRE_SECONDS")

    _cdn_domain = env("B2_CDN_DOMAIN")
    if _cdn_domain:
        if B2_SIGNED_URLS:
            # storages builds the url from the custom domain and returns it
            # unsigned (s3.py url()), so a CDN in front of a private bucket
            # would serve 401s. Fail loudly rather than at request time.
            raise ImproperlyConfigured(
                "B2_CDN_DOMAIN cannot be combined with B2_SIGNED_URLS: urls "
                "built from a custom domain are never signed. Use a public "
                "bucket with the CDN, or drop the CDN."
            )
        AWS_S3_CUSTOM_DOMAIN = _cdn_domain

    STORAGES = {
        "default": {"BACKEND": "storages.backends.s3.S3Storage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
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
