import os
import environ
from pathlib import Path
from celery import Celery


env = environ.Env(DEBUG=(bool, False))
BASE_DIR = Path(__file__).resolve().parent.parent
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))


# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "field_force.settings")


app = Celery("field_force")


# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# set broker url
app.conf.broker_url = env("RABBITMQ_BROKER_URL")

# this allows you to schedule items in the Django admin.
app.conf.beat_scheduler = "django_celery_beat.schedulers.DatabaseScheduler"
