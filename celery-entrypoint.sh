#!/bin/bash

echo "-----Running Celery entry point script-----"
source /root/empfly/venv/bin/activate
pip install -r celery_requirement.txt
pip install cryptography==37.0.4
pip install django-health-check==3.17.0
pip install psutil==5.9.5

# --no-input -> Suppresses all user prompts
python manage.py migrate

echo "-----CELERY-----"
pkill -9 -f 'celery'
celery -A field_force worker --pool=prefork --concurrency=2 --max-memory-per-child=262144 --loglevel=info