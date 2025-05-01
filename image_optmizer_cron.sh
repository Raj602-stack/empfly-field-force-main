#!/bin/bash

# enter inside the container & activate virtual environment & run script

docker exec ff-django bash -c "source ../../empfly/venv/bin/activate && python3 manage.py img_optimizer"