from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")
DEBUG = env.bool("DEBUG", default=True)
SECRET_KEY = env("SECRET_KEY", default="dev-only-cortalives" if DEBUG else environ.Env.NOTSET)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "testserver"])
DATABASES = {"default": env.db(default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")}
INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "allauth", "allauth.account", "allauth.socialaccount",
    "rest_framework", "drf_spectacular", "channels",
    "accounts", "dashboard", "videos", "streams", "transcriptions", "ai_engine",
    "clips", "rendering", "publishing", "analytics", "subscriptions", "notifications", "integrations",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware", "django.contrib.sessions.middleware.SessionMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.locale.LocaleMiddleware", "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware", "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "core.urls"
ASGI_APPLICATION = "core.asgi.application"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True, "OPTIONS": {"context_processors": [
        "django.template.context_processors.request", "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend", "allauth.account.auth_backends.AuthenticationBackend"]
AUTH_PASSWORD_VALIDATORS = [{"NAME": f"django.contrib.auth.password_validation.{name}"} for name in (
    "UserAttributeSimilarityValidator", "MinimumLengthValidator", "CommonPasswordValidator", "NumericPasswordValidator"
)]
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = env("EMAIL_VERIFICATION", default="optional" if DEBUG else "mandatory")
LOGIN_REDIRECT_URL = "/dashboard/"
ACCOUNT_LOGOUT_REDIRECT_URL = "/"
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=not DEBUG)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="CortaLives <no-reply@localhost>")
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "UTC"
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_ROOT = env("MEDIA_ROOT", default=str(BASE_DIR / "media"))
MEDIA_URL = "/media/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
if env("S3_BUCKET", default=""):
    STORAGES = {
        "default": {"BACKEND": "storages.backends.s3.S3Storage", "OPTIONS": {
            "bucket_name": env("S3_BUCKET"), "endpoint_url": env("S3_ENDPOINT", default=None),
            "region_name": env("AWS_REGION", default="us-east-1"), "default_acl": None,
            "file_overwrite": False, "querystring_auth": True, "querystring_expire": 120,
        }},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_EAGER", default=False)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_SOFT_TIME_LIMIT = 3300
CELERY_TASK_TIME_LIMIT = 3600
CELERY_BROKER_TRANSPORT_OPTIONS = {"visibility_timeout": 7200}
CELERY_TASK_ROUTES = {
    "videos.tasks.ingest": {"queue": "downloads"},
    "videos.tasks.transcribe": {"queue": "transcriptions"},
    "videos.tasks.analyze": {"queue": "analysis"},
    "videos.tasks.generate": {"queue": "clips"},
    "rendering.tasks.render_clip": {"queue": "rendering"},
    "publishing.tasks.dispatch_due": {"queue": "publishing"},
}
CELERY_BEAT_SCHEDULE = {
    "recover-processing": {"task": "videos.tasks.recover", "schedule": 120},
    "publication-schedules": {"task": "publishing.tasks.dispatch_due", "schedule": 60},
}
CHANNEL_LAYERS = {"default": {"BACKEND": "channels_redis.core.RedisChannelLayer", "CONFIG": {"hosts": [REDIS_URL]}}}
MAX_UPLOAD_BYTES = env.int("MAX_UPLOAD_BYTES", default=512 * 1024 * 1024)
MAX_VIDEO_SECONDS = env.int("MAX_VIDEO_SECONDS", default=7200)
WHISPER_MODEL = env("WHISPER_MODEL", default="tiny")
WHISPER_DEVICE = env("WHISPER_DEVICE", default="cpu")
WHISPER_COMPUTE_TYPE = env("WHISPER_COMPUTE_TYPE", default="int8")
WHISPER_CPU_THREADS = env.int("WHISPER_CPU_THREADS", default=4)
IMPORT_PROXY = env("IMPORT_PROXY", default="")
SEMANTIC_PROVIDER = env("SEMANTIC_PROVIDER", default="heuristic")
SEMANTIC_API_BASE = env("SEMANTIC_API_BASE", default="")
SEMANTIC_API_KEY = env("SEMANTIC_API_KEY", default="")
SEMANTIC_MODEL = env("SEMANTIC_MODEL", default="")
SCORE_WEIGHTS = {"semantic": 3, "audio": 2, "visual": 1, "context": 3, "technical": 1}
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination", "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.UserRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"user": "120/min"},
}
SPECTACULAR_SETTINGS = {"TITLE": "CortaLives API", "VERSION": "1.0.0"}
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=not DEBUG)
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
YOUTUBE_CLIENT_ID = env("YOUTUBE_CLIENT_ID", default="")
YOUTUBE_CLIENT_SECRET = env("YOUTUBE_CLIENT_SECRET", default="")
YOUTUBE_REDIRECT_URI = env("YOUTUBE_REDIRECT_URI", default="")
OAUTH_ENCRYPTION_KEY = env("OAUTH_ENCRYPTION_KEY", default="")
if env.bool("SHARED_CACHE", default=False):
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL}}
VIDEO_RETENTION_DAYS = env.int("VIDEO_RETENTION_DAYS", default=0)
CELERY_BEAT_SCHEDULE["purge-expired-media"] = {"task": "videos.tasks.purge_expired", "schedule": 3600}

if env("SENTRY_DSN", default=""):
    import sentry_sdk

    sentry_sdk.init(dsn=env("SENTRY_DSN"), send_default_pii=False)

GOOGLE_LOGIN_CLIENT_ID = env("GOOGLE_LOGIN_CLIENT_ID", default="")
GOOGLE_LOGIN_CLIENT_SECRET = env("GOOGLE_LOGIN_CLIENT_SECRET", default="")
if GOOGLE_LOGIN_CLIENT_ID and GOOGLE_LOGIN_CLIENT_SECRET:
    INSTALLED_APPS.append("allauth.socialaccount.providers.google")
    SOCIALACCOUNT_PROVIDERS = {"google": {"APPS": [{
        "client_id": GOOGLE_LOGIN_CLIENT_ID, "secret": GOOGLE_LOGIN_CLIENT_SECRET, "key": "",
    }]}}
