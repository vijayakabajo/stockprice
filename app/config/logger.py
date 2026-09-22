import os


def get_logging_config(env_type, base_dir):
    """
    Returns LOGGING dict for Django settings.
    env_type: 'local' / 'preproduction' / 'production'

    Local: logs to console only (fast feedback, no file cleanup to manage).
    Preprod/prod: logs to console (captured by the process manager / Docker)
    plus a daily-rotating file under logs/<env_type>/, keeping 14 days.
    """
    handlers = {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "default",
        },
    }
    root_handlers = ["console"]

    if env_type != "local":
        log_dir = os.path.join(base_dir, "logs", env_type)
        os.makedirs(log_dir, exist_ok=True)

        handlers["file"] = {
            "level": "INFO",
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": os.path.join(log_dir, "app.log"),
            "when": "midnight",
            "backupCount": 14,
            "encoding": "utf-8",
            "formatter": "default",
        }
        root_handlers.append("file")

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "[%(asctime)s][%(levelname)s][%(name)s] %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": handlers,
        "loggers": {
            "google": {
                "handlers": root_handlers,
                "level": "ERROR",
                "propagate": False,
            },
            "urllib3": {
                "handlers": root_handlers,
                "level": "WARNING",
                "propagate": False,
            },
        },
        "root": {
            "handlers": root_handlers,
            "level": "DEBUG" if env_type == "local" else "INFO",
        },
    }
