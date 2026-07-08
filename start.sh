#!/bin/bash

# Start Celery worker in the background
celery -A online_judge worker -l info &

# Start Gunicorn in the foreground
exec gunicorn online_judge.wsgi:application \
     --bind 0.0.0.0:8000 \
     --workers 2 \
     --max-requests 1000 \
     --max-requests-jitter 100 \
     --timeout 120 \
     --keep-alive 2
