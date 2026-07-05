FROM python:3.13-slim

# Install system packages with security updates
RUN apt-get update && apt-get install -y \
    g++ \
    default-jdk \
    nodejs \
    npm \
    gcc \
    libmagic1 \
    libmagic-dev \
    sudo \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser -m appuser

# Create isolated sandbox user
RUN groupadd -r sandboxuser && useradd -r -g sandboxuser -m sandboxuser

# Allow appuser to run commands as sandboxuser without password
RUN echo "appuser ALL=(sandboxuser) NOPASSWD: ALL" >> /etc/sudoers

# Security environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV DJANGO_SETTINGS_MODULE=online_judge.settings

WORKDIR /app

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir python-magic pillow

# Copy application code
COPY . .

# Create necessary directories with proper permissions
RUN mkdir -p /app/media/profile_photos \
    && mkdir -p /app/staticfiles \
    && chown -R appuser:appuser /app \
    && chmod -R 700 /app

# Create completely isolated sandbox directory
RUN mkdir -p /sandbox \
    && chown -R sandboxuser:sandboxuser /sandbox \
    && chmod -R 777 /sandbox

# Collect static files
RUN python manage.py collectstatic --noinput

# Set security limits in the container
RUN echo "appuser soft nproc 100" >> /etc/security/limits.conf \
    && echo "appuser hard nproc 200" >> /etc/security/limits.conf \
    && echo "appuser soft nofile 1024" >> /etc/security/limits.conf \
    && echo "appuser hard nofile 2048" >> /etc/security/limits.conf

# Switch to non-root user
USER appuser

EXPOSE 8000

# Use gunicorn with security settings
CMD ["gunicorn", "online_judge.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--max-requests", "1000", \
     "--max-requests-jitter", "100", \
     "--timeout", "120", \
     "--keep-alive", "2"]
