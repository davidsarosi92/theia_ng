"""Minimal Django settings for the Theia NG test suite."""

SECRET_KEY = "theia-ng-test-key"
DEBUG = True

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "theia_ng",
    "tests.testproject.sampleapp",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]

ROOT_URLCONF = "tests.testproject.urls"

USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

THEIA_NG = {
    "SITE_TITLE": "Test Admin",
}
