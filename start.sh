#!/bin/bash

# Start Celery worker in the background (concurrency=1 for 512MB RAM limit)
celery -A online_judge worker -l info --concurrency=1 &

# Start Gunicorn in the foreground (workers=1 for 512MB RAM limit)
exec gunicorn online_judge.wsgi:application \
     --bind 0.0.0.0:8000 \
     --workers 1 \
     --max-requests 1000 \
     --max-requests-jitter 100 \
     --timeout 120 \
     --keep-alive 2
