import os
from urllib.parse import parse_qsl, unquote, urlsplit


def _from_url(url):
    """
    Splits a postgres://user:password@host:port/name?sslmode=... URL (the
    form Render and most hosts hand out) into Django's connection fields.
    """
    parts = urlsplit(url)
    return {
        "NAME": unquote(parts.path.lstrip("/")),
        "USER": unquote(parts.username or ""),
        "PASSWORD": unquote(parts.password or ""),
        "HOST": parts.hostname or "",
        "PORT": str(parts.port or 5432),
        "OPTIONS": dict(parse_qsl(parts.query)),
    }


def get_database_config():
    """
    Returns the DATABASES dict, entirely env-driven.

    Either DATABASE_URL (set by render.yaml from the Render Postgres
    connection string) or, when it is unset, the separate vars
    DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT (see .env.example).

    Need a read-replica or master/replica split later? Add a second entry
    to this dict (e.g. 'replica') and point it at replica env vars, then
    wire up a DATABASE_ROUTERS class in settings.py.
    """
    database_url = os.getenv("DATABASE_URL", "")
    if database_url:
        connection = _from_url(database_url)
    else:
        connection = {
            "NAME": os.getenv("DB_NAME", "shareprice_db"),
            "USER": os.getenv("DB_USER", "postgres"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", "5432"),
        }

    return {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            **connection,
            # Reuse connections for 60s instead of reconnecting per request;
            # health check avoids broken pipes on stale ones.
            "CONN_MAX_AGE": 60,
            "CONN_HEALTH_CHECKS": True,
        }
    }
