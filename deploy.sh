#!/bin/bash

# Deployment script with security fixes

echo "Starting secure deployment..."

# Stop existing containers
docker-compose down

# Build new images
docker-compose build

# Start services
docker-compose up -d

# Wait for services to start
sleep 10

# Run migrations
docker-compose exec web python manage.py makemigrations
docker-compose exec web python manage.py migrate

# Fix media permissions
docker-compose exec web python manage.py fix_media_permissions

# Collect static files
docker-compose exec web python manage.py collectstatic --noinput

# Restart nginx to ensure proper configuration
docker-compose restart nginx

echo "Deployment completed with security fixes!"
echo "Profile photos should now be visible at your domain."