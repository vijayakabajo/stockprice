import os
from urllib.parse import urlsplit, urlunsplit

REDIS_URL = os.getenv("REDIS_URL", "")
REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")


def redis_url(db):
    """
    The Redis URL for one logical DB index.

    REDIS_URL (set by render.yaml from the Render Key Value connection
    string, e.g. redis://red-xxxx:6379) wins when set; any DB index on it is
    replaced, so the cache and Celery still get their own DBs. Otherwise the
    URL is built from REDIS_HOST and REDIS_PORT.
    """
    if REDIS_URL:
        parts = urlsplit(REDIS_URL)
        return urlunsplit((parts.scheme, parts.netloc, f"/{db}", parts.query, ""))
    return f"redis://{REDIS_HOST}:{REDIS_PORT}/{db}"


def get_cache_config(env_type):
    """
    Returns CACHES dict for Django settings.
    Each env gets its own Redis DB index so local/preprod/prod never collide
    when they happen to share a Redis instance.
    """
    cache_redis_db = 1 if env_type == "production" else 2 if env_type == "preproduction" else 0

    return {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": redis_url(cache_redis_db),
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "SOCKET_CONNECT_TIMEOUT": 5,
                "SOCKET_TIMEOUT": 5,
                "THREAD_LOCAL": True,
            },
            "TIMEOUT": 3600,
        }
    }


# Cache TTLs (seconds) — examples, adjust per project
CACHE_TTL_DEFAULT = 300  # 5 minutes
