import os

from celery import Celery

from app.config.celery import get_celery_config

# Tell Celery which Django settings module to use
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")

app = Celery("app")

# Load Django settings into Celery (picks up INSTALLED_APPS etc.)
app.config_from_object("django.conf:settings", namespace="CELERY")

# Apply our environment-aware config
env_type = os.getenv("ENV_TYPE", "local").lower()
app.conf.update(get_celery_config(env_type))

# Auto-discover tasks from all INSTALLED_APPS (looks for tasks.py in each app)
app.autodiscover_tasks()
