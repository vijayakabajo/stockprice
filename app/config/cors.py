import os

from corsheaders.defaults import default_headers

ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "*").split(",") if h.strip()]

# Render sets this to the service's own <name>.onrender.com host. Always
# allow it, so the default URL works before a custom domain is attached.
RENDER_EXTERNAL_HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME", "")
if RENDER_EXTERNAL_HOSTNAME and "*" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

# CORS
CORS_ALLOW_ALL_ORIGINS = os.getenv("CORS_ALLOW_ALL_ORIGINS", "True") == "True"
# The API is read-only and has no auth, so browsers only ever need GET.
CORS_ALLOW_METHODS = ["GET", "HEAD", "OPTIONS"]
CORS_ALLOW_HEADERS = list(default_headers)

# CSRF — add your own domains via CSRF_TRUSTED_ORIGINS in .env (comma-separated)
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]
if RENDER_EXTERNAL_HOSTNAME:
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_EXTERNAL_HOSTNAME}")

# Middleware (order matters — CORS must be before CommonMiddleware)
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    # Serves /static/ itself, precompressed, and returns before anything below.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    # Compresses pages and API responses. Above every middleware that reads or
    # writes the body; below WhiteNoise, so static files are never recompressed.
    "django.middleware.gzip.GZipMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
