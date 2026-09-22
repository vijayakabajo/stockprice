import os


def get_database_config():
    """
    Returns the DATABASES dict, entirely env-driven.

    Required env vars (see .env.example):
        DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT

    Need a read-replica or master/replica split later? Add a second entry
    to this dict (e.g. 'replica') and point it at replica env vars, then
    wire up a DATABASE_ROUTERS class in settings.py.
    """
    return {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", "shareprice_db"),
            "USER": os.getenv("DB_USER", "postgres"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", "5432"),
            # Reuse connections for 60s instead of reconnecting per request;
            # health check avoids broken pipes on stale ones.
            "CONN_MAX_AGE": 60,
            "CONN_HEALTH_CHECKS": True,
        }
    }
