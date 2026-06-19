"""
Django settings for the INPACT / Ireland GHG Policy Impact Explorer platform.

Designed to run both locally and on Vercel's zero-configuration Django runtime.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
# In production (Vercel), set SECRET_KEY as an environment variable.
SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "dev-only-insecure-key-change-me-in-production",
)

# DEBUG is off by default. Locally you can export DEBUG=1 to turn it on.
DEBUG = os.environ.get("DEBUG", "0") == "1"

# Vercel serves your app on *.vercel.app. Localhost covers local development.
ALLOWED_HOSTS = [".vercel.app", "localhost", "127.0.0.1"]

# Vercel sits behind a proxy that terminates HTTPS.
CSRF_TRUSTED_ORIGINS = ["https://*.vercel.app"]

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
# Kept intentionally lean: the platform only serves a self-contained HTML page,
# so we avoid auth/sessions/DB machinery entirely.
INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "explorer",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise serves the files in explorer/static/ (e.g. /static/img/*.jpg)
    # directly from the app, so images work locally regardless of DEBUG and on
    # any host. On Vercel it coexists happily with the CDN that serves /static/.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "inpact_platform.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    },
]

WSGI_APPLICATION = "inpact_platform.wsgi.application"

# ---------------------------------------------------------------------------
# Database (not used by the page, but Django expects a config)
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-ie"
TIME_ZONE = "Europe/Dublin"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------
# Vercel automatically runs collectstatic during the build when STATIC_ROOT
# is set, and serves the result from its CDN. The page itself inlines its
# images, so there is little to collect, but this keeps the build happy.
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Let WhiteNoise resolve static files via the staticfiles finders at runtime,
# so /static/img/*.jpg is served straight from explorer/static/ without having
# to run `collectstatic` first during local development. Vercel still runs
# collectstatic during its build, which keeps production serving from STATIC_ROOT.
WHITENOISE_USE_FINDERS = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
