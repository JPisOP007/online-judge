#!/bin/bash

# Start Celery worker in the background (concurrency=1 for 512MB RAM limit)
celery -A online_judge worker -l info --concurrency=1 &

# Start Gunicorn in the foreground (workers=1 for 512MB RAM limit)
# One worker still, to stay inside 512MB, but threaded rather than sync: the
# default sync worker serves exactly one request at a time, so every visitor
# queued behind the one in front. These views are I/O-bound on MongoDB, so
# threads buy real concurrency for almost no memory.
exec gunicorn online_judge.wsgi:application \
     --bind 0.0.0.0:8000 \
     --workers 1 \
     --worker-class gthread \
     --threads 8 \
     --max-requests 1000 \
     --max-requests-jitter 100 \
     --timeout 120 \
     --keep-alive 2
