#!/bin/bash

echo "-----Running Django entry point script-----"
source /root/empfly/venv/bin/activate
pip install -r requirements.txt
pip install cryptography==37.0.4
pip install gunicorn
pip install django-health-check==3.17.0
pip install psutil==5.9.5

# --no-input -> Suppresses all user prompts
python manage.py migrate --no-input

echo "-----DJANGO-----"
# python manage.py runserver 0.0.0.0:8000
gunicorn --bind 0.0.0.0:8000 field_force.wsgi --workers=3 --timeout=300
