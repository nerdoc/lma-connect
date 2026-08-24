"""
Django settings for LMA Connect.

Configured through environment variables (see .env.example).
Required in production: SECRET_KEY, ALLOWED_HOSTS, DEBUG=False, DB_*.
"""

import os
from pathlib import Path

from csp.constants import NONCE
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: list[str] | None = None) -> list[str]:
    raw = os.environ.get(name)
    if not raw:
        return default or []
    return [item.strip() for item in raw.split(",") if item.strip()]


# ──────────────────────────────────────────────
# Core
# ──────────────────────────────────────────────

DEBUG = env_bool("DJANGO_DEBUG", default=False)

# A fallback is fine in dev; in production DJANGO_SECRET_KEY is mandatory.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-only-do-not-use-in-prod"  # noqa: S105
    else:
        raise RuntimeError("DJANGO_SECRET_KEY env var is required when DEBUG=False")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

ROOT_URLCONF = "lma_connect.urls"
WSGI_APPLICATION = "lma_connect.wsgi.application"
ASGI_APPLICATION = "lma_connect.asgi.application"



# ──────────────────────────────────────────────
# Apps
# ──────────────────────────────────────────────

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "django_htmx",
    "markdownify",
    "axes",
    "csp",
]

# django-markdownify: lean default — safe HTML tags only.
MARKDOWNIFY = {
    "default": {
        "WHITELIST_TAGS": [
            "a", "abbr", "acronym", "b", "blockquote", "br", "code", "em",
            "i", "li", "ol", "p", "pre", "strong", "ul", "h2", "h3", "h4",
            "hr", "table", "thead", "tbody", "tr", "th", "td",
        ],
        "WHITELIST_ATTRS": ["href", "src", "alt", "title"],
        # tables: privacy policies typically inform under GDPR Art. 13 in two
        # tables (processing activities, retention periods). Without the
        # extension those render as a desert of pipe characters — which is why
        # the table tags are on the whitelist above.
        "MARKDOWN_EXTENSIONS": ["markdown.extensions.fenced_code",
                                "markdown.extensions.tables"],
        "STRIP": True,
        "BLEACH": True,
    }
}

# Plugin apps — switch features on/off centrally here.
# Order matters: core first (Event, ConsentRecord, Room, Committee), then the
# rest; people before program (Speaker → SessionSpeaker FK).
LOCAL_PLUGINS = [
    "lma_connect.plugins.core.apps.CoreConfig",
    "lma_connect.plugins.people.apps.PeopleConfig",
    "lma_connect.plugins.program.apps.ProgramConfig",
    "lma_connect.plugins.sponsors.apps.SponsorsConfig",
    "lma_connect.plugins.abstracts.apps.AbstractsConfig",
    "lma_connect.plugins.feedback.apps.FeedbackConfig",
    "lma_connect.plugins.access.apps.AccessConfig",
    "lma_connect.plugins.qr.apps.QrConfig",
    "lma_connect.plugins.gamification.apps.GamificationConfig",
    "lma_connect.plugins.expo.apps.ExpoConfig",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_PLUGINS


# ──────────────────────────────────────────────
# Middleware
# ──────────────────────────────────────────────

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise is loaded as a WSGI wrapper in wsgi.py (not as middleware)
    # so that an explicit static_prefix=/static/ can be set. Background: with
    # FORCE_SCRIPT_NAME=/conf, STATIC_URL stays /conf/static/ for template URL
    # generation, but the reverse proxy strips /conf before the backend — so
    # WhiteNoise itself has to serve under /static/.
    "csp.middleware.CSPMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    # Custom LocaleMiddleware subclass: ignores Accept-Language so that the
    # configured LANGUAGE_CODE is everyone's default (other languages only via
    # the in-app switcher).
    "lma_connect.plugins.core.middleware.DefaultLanguageMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    # AxesMiddleware MUST come last.
    "axes.middleware.AxesMiddleware",
]


# ──────────────────────────────────────────────
# Templates
# ──────────────────────────────────────────────

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
                "lma_connect.plugins.core.context_processors.active_event",
                "lma_connect.plugins.core.context_processors.app_meta",
                "lma_connect.plugins.abstracts.context_processors.review_counts",
                "lma_connect.plugins.access.context_processors.is_ops",
            ],
        },
    },
]


# ──────────────────────────────────────────────
# Database
# ──────────────────────────────────────────────

DB_ENGINE = os.environ.get("DB_ENGINE", "sqlite").lower()

if DB_ENGINE == "mariadb" or DB_ENGINE == "mysql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.environ["DB_NAME"],
            "USER": os.environ["DB_USER"],
            "PASSWORD": os.environ["DB_PASSWORD"],
            "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
            "PORT": os.environ.get("DB_PORT", "3306"),
            "OPTIONS": {
                "charset": "utf8mb4",
                "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
    }
else:
    # SQLite under load (conference day, ~100 concurrent users):
    #
    # * journal_mode=WAL — readers do not block writers and vice versa.
    #   Without WAL every read serialises against every write.
    # * synchronous=NORMAL — safe against process crashes in WAL mode (only a
    #   power cut at the wrong moment can cost the last transaction) and saves
    #   a great many fsyncs compared to FULL.
    # * timeout — SQLite's busy_timeout in seconds. Django's default of 5 s is
    #   too tight once many attendees write QR scans, votes and feedback at the
    #   same time; past the timeout you get "database is locked".
    # * transaction_mode=IMMEDIATE — the actual fix for "database is locked".
    #   With the default (DEFERRED) a transaction starts as a reader and only
    #   asks for the write lock on the first UPDATE. If it collides with
    #   another writer there, SQLite raises SQLITE_BUSY *immediately* — the
    #   busy_timeout deliberately does not apply to that lock upgrade, because
    #   waiting would deadlock. IMMEDIATE takes the lock up front, so waiting
    #   goes through the timeout as intended.
    # * cache_size=-16000 → 16 MB page cache per connection (negative = KiB).
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
            # Persistent connections save the connect + PRAGMA setup on every
            # request. With gthread workers each thread holds exactly one
            # connection — 3 workers à 4 threads means 12 in total.
            "CONN_MAX_AGE": int(os.environ.get("DJANGO_CONN_MAX_AGE", "60")),
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": {
                "timeout": int(os.environ.get("DJANGO_SQLITE_TIMEOUT", "20")),
                "transaction_mode": "IMMEDIATE",
                "init_command": (
                    "PRAGMA journal_mode=WAL;"
                    "PRAGMA synchronous=NORMAL;"
                    "PRAGMA temp_store=MEMORY;"
                    "PRAGMA cache_size=-16000;"
                ),
            },
        }
    }


# ──────────────────────────────────────────────
# Cache & Sessions
# ──────────────────────────────────────────────
# LocMemCache on purpose, not Redis/Memcached: shared hosting rarely offers a
# cache daemon, and the operational cost is not worth it for an app this size.
# The cache is per Gunicorn worker — harmless here, because it is used purely
# as a read accelerator and the database always stays the source of truth.
# `MAX_ENTRIES` is generous so sessions are not evicted all the time.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "lma-connect",
        "TIMEOUT": 300,
        "OPTIONS": {"MAX_ENTRIES": 5000, "CULL_FREQUENCY": 4},
    }
}

# cached_db: session reads go through the process cache, writes still go to
# the database. Every request of a logged-in user saves one SELECT on
# django_session — with 100 attendees constantly navigating program and Q&A
# that is the cheapest win in DB load available here. Logout/invalidation is
# unaffected because the database remains authoritative.
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
SESSION_COOKIE_AGE = int(os.environ.get("DJANGO_SESSION_COOKIE_AGE", str(60 * 60 * 24 * 14)))
# Keep the default of False: otherwise EVERY request writes the session back
# to the database and undoes the win above.
SESSION_SAVE_EVERY_REQUEST = False


# ──────────────────────────────────────────────
# Auth & Passwords
# ──────────────────────────────────────────────

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTH_USER_MODEL = "lma_core.User"

LOGIN_URL = "login"  # URL name instead of a path → tolerant of FORCE_SCRIPT_NAME
LOGIN_REDIRECT_URL = "core:home"
LOGOUT_REDIRECT_URL = "core:home"

# django-axes: AxesStandaloneBackend first, then the Django default.
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]


# ──────────────────────────────────────────────
# Internationalization
# ──────────────────────────────────────────────
# TIME_ZONE is the server-side default for rendering naive datetimes. Each
# event additionally carries its own `timezone_name`, so an event abroad does
# not need a settings change.

LANGUAGE_CODE = os.environ.get("DJANGO_LANGUAGE_CODE", "en")
TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", "Europe/Vienna")
USE_I18N = True
USE_TZ = True

LANGUAGES = [
    ("en", "English"),
    ("de", "Deutsch"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]


# ──────────────────────────────────────────────
# Static & Media
# ──────────────────────────────────────────────

# URL prefix for sub-path deployments (e.g. example.org/conference/).
# When set, Django generates every URL (including STATIC/MEDIA) with that
# prefix. An Uberspace backend has to be registered with `--prefix keep`.
FORCE_SCRIPT_NAME = os.environ.get("DJANGO_FORCE_SCRIPT_NAME") or None
_PREFIX = (FORCE_SCRIPT_NAME or "").rstrip("/")

STATIC_URL = f"{_PREFIX}/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
# WhiteNoise: compressed + hashed filenames, so assets can be cached hard
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

MEDIA_URL = f"{_PREFIX}/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Scope the session/CSRF cookies to the prefix, otherwise they collide with
# the cookies of whatever else is served from the same hostname (catch-all
# on "/").
if _PREFIX:
    SESSION_COOKIE_PATH = _PREFIX + "/"
    CSRF_COOKIE_PATH = _PREFIX + "/"
    LANGUAGE_COOKIE_PATH = _PREFIX + "/"


# ──────────────────────────────────────────────
# Default primary key
# ──────────────────────────────────────────────

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ──────────────────────────────────────────────
# Security headers (effective in prod, harmless in dev)
# ──────────────────────────────────────────────

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_REFERRER_POLICY = "same-origin"
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


# ──────────────────────────────────────────────
# django-axes — brute-force protection
# ──────────────────────────────────────────────
# Lockout after 10 failed attempts per (user|ip), cool-off 1 h.
# Token login: tokens are handled in /t/<token>/, where Axes does not kick in
# automatically — see the access plugin for the token-redeem throttling.
AXES_ENABLED = env_bool("DJANGO_AXES_ENABLED", default=True)
# No separate "AXES" block on the admin index: the three models are registered
# as proxies under "Access", where they belong (see access/models.py).
AXES_ENABLE_ADMIN = False
AXES_FAILURE_LIMIT = int(os.environ.get("DJANGO_AXES_FAILURE_LIMIT", "10"))
AXES_COOLOFF_TIME = float(os.environ.get("DJANGO_AXES_COOLOFF_HOURS", "1"))
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = "axes/locked_out.html"
# Behind a reverse proxy: honour X-Forwarded-For.
AXES_IPWARE_PROXY_COUNT = int(os.environ.get("DJANGO_AXES_PROXY_COUNT", "0")) or None
AXES_IPWARE_META_PRECEDENCE_ORDER = ["HTTP_X_FORWARDED_FOR", "REMOTE_ADDR"]


# ──────────────────────────────────────────────
# Content-Security-Policy (django-csp 4.x)
# ──────────────────────────────────────────────
# script-src: NONCE for inline scripts (request.csp_nonce in templates), no
# 'unsafe-inline' → real XSS protection for JavaScript.
# style-src: 'unsafe-inline' stays — Tabler uses inline style="" attributes in
# many components, which a nonce does not cover (CSP3 would need
# 'unsafe-hashes'; not worth the effort for CSS).

_csp_report_only = env_bool("DJANGO_CSP_REPORT_ONLY", default=False)

_csp_policy = {
    "DIRECTIVES": {
        "default-src": ["'self'"],
        # No third-party domains: Tabler, the icon font and htmx live under
        # static/vendor/ and are served from our own host (see base.html).
        "script-src": [
            "'self'",
            NONCE,
        ],
        "style-src": [
            "'self'",
            "'unsafe-inline'",  # Tabler uses inline style=""; acceptable for CSS
        ],
        # No "https:" here — the shipped privacy policy promises that the CSP
        # allows no external sources at all and that the browser contacts no
        # third party during use. An open img-src would undercut that
        # (markdownify does not let <img> through anyway); every image is an
        # upload from MEDIA_ROOT.
        "img-src": ["'self'", "data:"],
        "font-src": ["'self'", "data:"],
        "connect-src": ["'self'"],
        "frame-ancestors": ["'none'"],
        "form-action": ["'self'"],
        "base-uri": ["'self'"],
        "object-src": ["'none'"],
    },
}

if _csp_report_only:
    CONTENT_SECURITY_POLICY_REPORT_ONLY = _csp_policy
else:
    CONTENT_SECURITY_POLICY = _csp_policy


# ──────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO"},
        "lma_connect": {"handlers": ["console"], "level": "DEBUG" if DEBUG else "INFO"},
    },
}
