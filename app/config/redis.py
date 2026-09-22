import os

REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")


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
            "LOCATION": f"redis://{REDIS_HOST}:{REDIS_PORT}/{cache_redis_db}",
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
