import os

from celery.schedules import crontab


def get_celery_config(env_type):
    """
    Returns the full Celery configuration dict for the given env_type.

    Redis DB allocation:
        production     -> DB 3
        preproduction  -> DB 4
        local          -> DB 0

    Keeping separate Redis DBs per environment prevents tasks from one
    environment bleeding into another when multiple envs share the same
    Redis instance.
    """
    env_type = (env_type or "local").lower()

    celery_redis_db = (
        3 if env_type == "production" else 4 if env_type == "preproduction" else 0  # local / fallback
    )

    redis_host = os.getenv("REDIS_HOST", "127.0.0.1")
    redis_port = os.getenv("REDIS_PORT", "6379")

    broker = f"redis://{redis_host}:{redis_port}/{celery_redis_db}"
    backend = broker

    return {
        # -- Broker & backend --------------------------------------------
        "broker_url": broker,
        "result_backend": backend,
        # -- Serialisation -------------------------------------------------
        "task_serializer": "json",
        "result_serializer": "json",
        "accept_content": ["json"],
        # -- Timezone --------------------------------------------------------
        # UTC, matching Django's TIME_ZONE. U.S. market sessions are derived
        # explicitly in America/New_York by the sync code, not from here.
        "timezone": "UTC",
        "enable_utc": True,
        # -- Task behaviour ----------------------------------------------------
        # Acknowledge task only after it completes, not when received.
        # Prevents task loss if the worker crashes mid-execution.
        "task_acks_late": True,
        # Discard tasks that have no registered handler (avoids silent drops)
        "task_reject_on_worker_lost": True,
        # -- Result expiry -----------------------------------------------------
        # Keep results for 1 hour - enough for polling, not enough to bloat Redis
        "result_expires": 3600,
        # -- Beat schedule -------------------------------------------------------
        # Times are UTC. Extended-hours trading ends at 20:00 ET, which is
        # 00:00 UTC in summer (EDT) and 01:00 UTC in winter (EST), so both
        # jobs below run after the session is final all year round.
        "beat_schedule": {
            # Ticker master, then company profiles. Runs first so tickers
            # that listed today exist before their prices arrive.
            "sync-reference-data-daily": {
                "task": "sync.tasks.sync_reference_data_task",
                "schedule": crontab(hour=1, minute=15),
            },
            # Tue-Sat UTC covers the Mon-Fri sessions. With no arguments the
            # task also re-syncs any recent session that has not succeeded.
            "sync-daily-prices": {
                "task": "sync.tasks.sync_daily_prices_task",
                "schedule": crontab(hour=1, minute=45, day_of_week="tue-sat"),
            },
        },
    }
