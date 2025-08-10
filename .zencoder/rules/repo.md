---
description: Repository Information Overview
alwaysApply: true
---

# Online Judge Information

## Summary
A Django-based online judge platform for coding competitions and problem-solving. The system allows users to submit solutions in multiple programming languages, participate in contests, and receive automated evaluations of their code.

## Structure
- **core/**: Main application with models, views, and business logic
- **online_judge/**: Django project settings and configuration
- **templates/**: HTML templates for the web interface
- **static/**: CSS and image assets
- **media/**: User-uploaded files (profile photos, submissions)
- **nginx/**: Web server configuration for production deployment
- **credentials/**: API keys and service account credentials

## Language & Runtime
**Language**: Python
**Version**: 3.11 (in production), 3.13 (in development)
**Framework**: Django 5.1.6
**Build System**: Django's built-in management commands
**Package Manager**: pip

## Dependencies
**Main Dependencies**:
- Django 5.1.6
- django-codemirror6 1.0.1
- django-widget-tweaks 1.5.0
- djangorestframework 3.15.2
- google-cloud-aiplatform (for AI code review)
- gunicorn (for production deployment)
- whitenoise (for static file serving)
- Pillow (for image processing)

## Build & Installation
```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py runserver
```

## Docker
**Dockerfile**: Dockerfile
**Image**: Python 3.11-slim with additional runtimes (Java 17, Node.js)
**Configuration**: Multi-container setup with web app, nginx, and certbot
**Run Command**:
```bash
docker-compose up -d
```

## Testing
**Test Files**: 
- test_ai_admin.py
- test_fixes.py
- test_security.py
- core/tests.py

## Application Features
**Code Execution**:
- Supports Python, C++, Java, and JavaScript
- Secure execution environment with resource limits
- Time limit: 5 seconds, Memory limit: 128MB

**Contest System**:
- Timed coding competitions
- Leaderboard and standings
- Problem sets with difficulty levels
- Participant registration and management

**Security**:
- Custom security middleware
- Rate limiting and request size limits
- Secure file upload validation
- Non-root Docker user for production