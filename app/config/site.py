"""
The public site: identity, absolute URLs, release tag and IndexNow.

SITE_URL is the only source of absolute URLs (canonical links, sitemaps,
Open Graph, JSON-LD). Pages are cached and shared, so they must never be
built from a request's Host header.
"""

import os
import time

# RENDER_EXTERNAL_URL (https://<name>.onrender.com) is a fallback for the
# web service before a custom domain is set. The Celery worker has no
# external URL, so SITE_URL must be set explicitly in production.
SITE_URL = (
    os.getenv("SITE_URL")
    or os.getenv("HOST_URL")
    or os.getenv("RENDER_EXTERNAL_URL")
    or "http://localhost:8000"
).rstrip("/")
SITE_NAME = os.getenv("SITE_NAME", "Equity Profiles")
SITE_TAGLINE = "Answer-first profiles of every U.S. listed company"
SITE_DESCRIPTION = (
    "Answer-first profiles of U.S. listed companies: market cap, sector, exchange, headcount, "
    "identifiers and filings, every figure dated and sourced."
)
SITE_LANGUAGE = "en-US"
SITE_LOCALE = "en_US"
SITE_TWITTER = os.getenv("SITE_TWITTER", "")  # "@handle", optional

# The publisher shown in Organization structured data and the footer.
ORGANIZATION = {
    "name": os.getenv("ORGANIZATION_NAME", "6sMarketers"),
    "url": os.getenv("ORGANIZATION_URL", "https://6smarketers.com"),
    "email": os.getenv("ORGANIZATION_EMAIL", "connect@6smarketers.com"),
    "same_as": [u.strip() for u in os.getenv("ORGANIZATION_SAME_AS", "").split(",") if u.strip()],
}

# Identifies a deploy. Part of every HTML cache key, so a deploy (new
# templates, new hashed static names) never serves pages rendered by the old
# code. Set it to the git SHA in deploys; the fallback is the process start
# time, which is correct but shares less cache between workers. On Render,
# RENDER_GIT_COMMIT is set to the deployed SHA automatically.
RELEASE = os.getenv("RELEASE") or os.getenv("RENDER_GIT_COMMIT") or str(int(time.time()))

# IndexNow (Bing, Yandex, Seznam, Naver...): ping changed URLs after a sync.
# The key is any 8-128 character [a-zA-Z0-9-] string; it is also served at
# /<key>.txt to prove we own the host. Pings only go out when enabled, which
# by default means production with a key set.
INDEXNOW_KEY = os.getenv("INDEXNOW_KEY", "")
INDEXNOW_ENDPOINT = os.getenv("INDEXNOW_ENDPOINT", "https://api.indexnow.org/indexnow")


def indexnow_enabled(env_type):
    default = "True" if env_type == "production" else "False"
    return bool(INDEXNOW_KEY) and os.getenv("INDEXNOW_ENABLED", default) == "True"
