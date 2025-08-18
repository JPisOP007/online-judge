---
description: Repository Information Overview
alwaysApply: true
---

# Online Judge Information

## Summary
A Django-based online judge platform for hosting programming contests and evaluating code submissions. The system supports multiple programming languages, contest management, user roles, and secure code execution.

## Structure
- **core/**: Main application with models, views, and business logic
- **online_judge/**: Django project settings and configuration
- **templates/**: HTML templates for the web interface
- **static/**: CSS and image assets
- **media/**: User-uploaded content (profile photos, submissions)
- **nginx/**: Web server configuration for production deployment
- **credentials/**: API keys and service account credentials

## Language & Runtime
**Language**: Python
**Version**: 3.11 (based on Dockerfile)
**Framework**: Django 5.1.6
**Database**: SQLite (default configuration)

## Dependencies
**Main Dependencies**:
- Django 5.1.6
- django-codemirror6 1.0.1
- django-widget-tweaks 1.5.0
- djangorestframework 3.15.2
- google-cloud-aiplatform (for AI code review)
- gunicorn (WSGI server)
- whitenoise (static file serving)
- Pillow (image processing)

**Development Dependencies**:
- virtualenv 20.31.2

## Build & Installation
```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Start development server
python manage.py runserver
```

## Docker
**Dockerfile**: Dockerfile
**Image**: Python 3.11-slim with additional compilers (g++, JDK 17, Node.js)
**Configuration**: Multi-container setup with web, nginx, and certbot services
**Run Command**:
```bash
docker-compose up -d
```

## Testing
**Framework**: Django's built-in testing framework
**Test Location**: core/tests.py
**Run Command**:
```bash
python manage.py test
```

## Application Features
**Code Execution**:
- Supports Python, C++, Java, and JavaScript
- Secure execution environment with resource limits
- Time and memory constraints for submissions

**Contest Management**:
- Create and manage programming contests
- Different contest types (rated, unrated, practice)
- Participant registration and standings
- Contest announcements

**User Roles**:
- Admin: Full system access
- Problem Setter: Create and manage problems
- Participant: Solve problems and participate in contests

**Security**:
- Custom security middleware
- Rate limiting and request size limits
- Secure file upload validation
- CSRF, XSS, and content-type security headers